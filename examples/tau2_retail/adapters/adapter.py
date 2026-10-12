"""tau2-bench adapter template — optimize the retail agent's POLICY + TOOLS.

Ready-to-use cap-evolve adapter for tau2-bench (https://github.com/sierra-research/tau2-bench).
Supports ANY litellm-compatible provider — configure via env vars (see model_config.py).

SETUP:
  1. Clone & install tau2-bench:
       git clone https://github.com/sierra-research/tau2-bench ../tau2-bench
       pip install -e ../tau2-bench

  2. Copy this directory to .capevolve/project/adapters/

  3. Set env vars (in .env or shell):
       MODEL=gpt-4.1-mini  OPENAI_API_KEY=sk-…       # OpenAI
       MODEL=anthropic/claude-sonnet-4-6  ANTHROPIC_API_KEY=…  # Anthropic
       MODEL=vertex_ai/claude-sonnet-4-6              # Vertex AI (ADC, no key)
       MODEL=ollama/qwen2.5:7b-instruct  API_BASE=http://localhost:11434  # local
       MODEL=litellm_proxy/my-model  LITELLM_PROXY_API_BASE=http://proxy:4000  LITELLM_PROXY_API_KEY=…

  4. Run: cap-evolve check && cap-evolve run

WHAT THIS OPTIMIZES:
  - The retail domain's system-prompt policy (policy/policy.md)
  - Optionally the tool implementations (tools/tools.py)

HOW IT WORKS:
  - tasks()      → all 50 retail tasks from tau2 (stable, no network).
  - run_batch()  → tau2's own batch runner (run_tasks) with your model.
  - score()      → tau2's own reward in [0,1] with gold-safe feedback.
  - apply()      → overrides the registry's retail env constructor.
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import json as _json
import threading as _threading

# ---- campaign model wiring (Suite B). All calls go through the campaign gateway; the API key is a
# non-secret metering tag "<TAU_TAG_PREFIX>:<role>" with role in {target, user, judge}. ----------
GATEWAY = os.environ.get("TAU_GATEWAY", "http://127.0.0.1:4111/v1")
AGENT_MODEL = os.environ.get("TAU_AGENT_MODEL", "openai/rits/openai/gpt-oss-120b-a100")
USER_SIM_MODEL = os.environ.get("TAU_USER_MODEL", "openai/rits/openai/gpt-oss-120b-a100")
JUDGE_MODEL = os.environ.get("TAU_JUDGE_MODEL", "openai/azure/gpt-5.5")  # lead decision: not the target/user model; default reasoning settings
SPLITS_JSON = Path(os.environ.get("TAU_SPLITS_JSON", Path(__file__).resolve().parents[3] / "protocol" / "tau_retail_splits.json"))
MAX_STEPS = int(os.environ.get("TAU_MAX_STEPS", "100"))


def _kwargs(role: str) -> dict:
    prefix = os.environ.get("TAU_TAG_PREFIX", "tag:E10B-adhoc-s0:adhoc")
    kw = {"api_base": GATEWAY, "api_key": f"{prefix}:{role}"}
    if role == "judge":
        jt = os.environ.get("TAU_JUDGE_TEMPERATURE", "").strip()
        if jt:   # Suite D: tau2-default judge (gpt-4.1) at temperature 0
            kw["temperature"] = float(jt)
        return kw   # gpt-5.x pins temperature; judge runs with provider-default settings (recorded as such)
    kw.update(temperature=0.0, max_tokens=int(os.environ.get("MAX_TOKENS", "8000")))
    eff = os.environ.get("TAU_REASONING_EFFORT", "").strip()
    if eff:
        kw["reasoning_effort"] = eff
        kw["allowed_openai_params"] = ["reasoning_effort"]
    return kw


class model_config:  # noqa: N801 - minimal shim for the template's call sites
    MODEL = AGENT_MODEL

    @staticmethod
    def llm_kwargs_for(role: str) -> dict:
        return _kwargs("target" if role == "agent" else role)


def _load_splits() -> dict:
    return _json.loads(SPLITS_JSON.read_text())


def _allowed_ids() -> set:
    """Ids the adapter may EVER evaluate: official retail TRAIN (opt + sel). The sealed official TEST
    ids are excluded here, so a task id from TEST can never be run by any search or pilot."""
    s = _load_splits()
    allowed = set(s["opt"]) | set(s["sel"])
    assert not allowed & set(s["sealed_test"]), "sealed test ids leaked into the allowed set"
    return allowed


def _seal_check(task_ids) -> None:
    s = _load_splits()
    bad = set(map(str, task_ids)) & set(s["sealed_test"])
    if bad and os.environ.get("TAU_ALLOW_SEALED_TEST") != "final-eval-only":
        raise RuntimeError(f"REFUSING to evaluate sealed official retail TEST ids: {sorted(bad)[:5]}")

DOMAIN = "retail"

# docs/TAU2_SUMMARY.md row 7: the tau2-bench user simulator sometimes emits ``###STOP###``
# in the SAME message as reasoning that explicitly plans to continue ("we must wait for
# agent's third message. Continue."), in 15/27 observed task-7 failures — ~4.2% of all
# rollouts lost to a simulator artifact that measures nothing about agent skill. tau2-bench
# is an external package (cloned at setup time, not vendored here), so the fix lives on our
# side of the boundary: detect the leak from the message trace and mark the rollout as
# infra noise, matching the existing ``rollout.error`` path below rather than scoring the
# agent down for a bug that is not the agent's.
_STOP_LEAK_RE = re.compile(
    r"###\s*stop\s*###.{0,400}\b(?:continue|continuing|wait\s+for|must\s+wait|"
    r"keep\s+(?:going|talking)|not\s+(?:done|finished)\s+yet)\b"
    r"|\b(?:continue|continuing|wait\s+for|must\s+wait|"
    r"keep\s+(?:going|talking)|not\s+(?:done|finished)\s+yet)\b.{0,400}###\s*stop\s*###",
    re.I | re.S,
)


def _leaked_stop_continuation(messages) -> bool:
    """True iff a user-simulator turn emits ``###STOP###`` alongside leaked reasoning that
    explicitly plans to continue the conversation. Only ``user``-role turns are checked —
    that is the simulator's own voice, not the agent's."""
    for m in messages or []:
        if not isinstance(m, dict) or m.get("role") != "user":
            continue
        content = m.get("content")
        if isinstance(content, str) and _STOP_LEAK_RE.search(content):
            return True
    return False


# ---------------------------------------------------------------------------
# Candidate building helpers (pure; no network)
# ---------------------------------------------------------------------------


def _max_concurrency(default: int = 100) -> int:
    """Rollout concurrency, honouring the runner's own knob first and the canonical one second.

    ``TAU2_MAX_CONCURRENCY`` is tau2's name and stays authoritative here, so an existing setup keeps
    working unchanged. ``CAPEVOLVE_MAX_CONCURRENCY`` is the benchmark-neutral name the optimization
    skills set, so they can control load without knowing which runner is underneath -- an algorithm
    that hardcodes one benchmark's variable is not an algorithm, it is a tau2 script.
    """
    for name in ("TAU2_MAX_CONCURRENCY", "CAPEVOLVE_MAX_CONCURRENCY"):
        raw = os.environ.get(name)
        if raw:
            try:
                return int(raw)
            except ValueError:
                pass
    return default


def _load_candidate_tools_class(tools_path: Path):
    """Import a candidate tools/tools.py and return its AirlineTools class."""
    if not tools_path.exists():
        return None, set()
    spec = importlib.util.spec_from_file_location(
        f"capevolve_candidate_tools_{abs(hash(str(tools_path)))}_{id(object())}",
        tools_path,
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    cls = getattr(mod, "RetailTools", None)
    remove = set(getattr(mod, "REMOVE_TOOLS", set()) or set())
    return cls, remove


def _build_candidate_tools(candidate_dir: Path):
    """Instantiate the candidate AirlineTools from tools/tools.py on the RetailDB."""
    from tau2.domains.retail.data_model import RetailDB
    from tau2.domains.retail.tools import RetailTools as _PristineRetailTools
    from tau2.domains.retail.utils import RETAIL_DB_PATH

    db = RetailDB.load(RETAIL_DB_PATH)
    tools_path = candidate_dir / "tools" / "tools.py"
    cand_cls, remove = _load_candidate_tools_class(tools_path)
    RetailToolsClass = cand_cls or _PristineRetailTools

    if not remove:
        return RetailToolsClass(db)

    _remove = set(remove)
    _base_get_tools = RetailToolsClass.get_tools

    def get_tools(self, include=None):
        tools_map = _base_get_tools(self, include=include)
        return {k: v for k, v in tools_map.items() if k not in _remove}

    def has_tool(self, tool_name: str) -> bool:
        return tool_name not in _remove and tool_name in self.tools

    CandidateTools = type(
        "CandidateRetailTools",
        (RetailToolsClass,),
        {"get_tools": get_tools, "has_tool": has_tool},
    )
    return CandidateTools(db)


#: Toolkit factory for the built-in pre-gate (#708): `pregate: {toolkit: <this file>:pregate_toolkit}`
#: in capevolve.yaml makes tool smoke + tool-call replay live (callable(candidate_dir) -> toolkit).
pregate_toolkit = _build_candidate_tools


def _read_candidate_policy(candidate_dir: Path) -> str:
    """Pristine tau2 retail policy (IMMUTABLE benchmark text, issue #563) followed by the candidate's
    editable agent-side guidance (``policy/policy.md``). The optimizer can add to what the agent is told
    but cannot soften, delete or rewrite a benchmark rule."""
    from tau2.domains.retail.utils import RETAIL_POLICY_PATH

    base = Path(RETAIL_POLICY_PATH).read_text(encoding="utf-8")
    path = candidate_dir / "policy" / "policy.md"
    extra = path.read_text(encoding="utf-8").strip() if path.exists() else ""
    if extra in ("", "(none)"):
        return base
    return base.rstrip() + "\n\n# Additional agent guidance\n\n" + extra + "\n"


_cost_unpriced_warned = False


def _user_model() -> str:
    return USER_SIM_MODEL


def _infra_detail(sim, messages) -> dict:
    """LOGGING ONLY: what tau2 recorded when a simulation ended with an infrastructure/unexpected error. tau2's run_with_retry stores
    ``sim.info = {error, error_type, error_traceback, failed_after_attempts}`` on its placeholder SimulationRun (messages=[]); for a sim that
    did produce messages, the last assistant tool call and the tool result that followed it are recorded. Never used for scoring or classification."""
    import re as _re
    d = {}
    info = getattr(sim, "info", None)
    info = info if isinstance(info, dict) else {}
    for k in ("error", "error_type", "failed_after_attempts"):
        if info.get(k) is not None:
            d[k] = info[k] if k != "error" else str(info[k])[:2000]
    tb = info.get("error_traceback")
    if tb:
        tb = str(tb)
        d["traceback_tail"] = tb[-3000:]
        d["traceback_functions"] = sorted(set(_re.findall(r"in ([A-Za-z_][A-Za-z0-9_]*)\n", tb)))[-40:]
    last_call = None
    for i, m in enumerate(messages or []):
        if isinstance(m, dict) and m.get("role") == "assistant" and m.get("tool_calls"):
            tc = m["tool_calls"][-1]
            res = None
            for n in (messages or [])[i + 1:]:
                if isinstance(n, dict) and n.get("role") == "tool":
                    res = str(n.get("content"))[:500]; break
            last_call = {"name": tc.get("name"), "arguments": tc.get("arguments"), "tool_result_head": res}
    if last_call:
        d["last_tool_call"] = last_call
    d["n_messages"] = len(messages or [])
    return d


def _usersim_meta(messages, model) -> dict:
    """User-simulator tokens whose cost the provider did NOT report (None or 0.0), so the
    harness can list-price exactly those and never double-count a provider-priced message."""
    ut = [getattr(m, "usage", None) or {} for m in messages
          if getattr(m, "role", None) == "user" and not getattr(m, "cost", None)]
    return {"model": model,
            "prompt_tokens": sum(int(u.get("prompt_tokens") or 0) for u in ut),
            "completion_tokens": sum(int(u.get("completion_tokens") or 0) for u in ut)}


def _cost_and_tokens(sim) -> tuple[float, int, dict]:
    """Cost and token usage for one simulation, plus metadata saying how solid the cost is.

    `sim.agent_cost`/`sim.user_cost` come from tau2's ``get_cost``, which is ALL-OR-NOTHING:
    it returns None the moment ANY non-tool message lacks a per-message ``cost``. The
    previous ``sim.agent_cost or 0.0`` therefore collapsed "the provider did not price this"
    into "$0.00", and every tau2 run has reported **$0.0000 of eval spend** despite real
    rollouts — so tau2 runs could not be costed at all, and a genuinely free run was
    indistinguishable from an unpriced one. `litellm_proxy/...` gateway aliases are exactly
    the case that goes unpriced, and that is what CI uses for every benchmark.

    What this does about it:
      * TOKENS are always recovered. tau2 exposes ``get_token_usage``, which SKIPS messages
        without usage instead of nulling the whole run, and the adapter was hardcoding
        ``tokens=0`` and discarding it. Tokens are the honest fallback unit: they are what
        the provider actually reports, and spend can be derived from them out-of-band.
      * COST falls back to summing the per-message ``cost`` values that ARE present, which
        beats zero when only a few messages are unpriced.
      * It deliberately does NOT price tokens from a public rate table. The gateway's real
        rates are not knowable here, and a fabricated dollar figure presented next to
        measured ones is worse than an absent one.
      * ``cost_source`` and ``messages_missing_cost`` record which of those happened, so a
        0.0 can be read as "unpriced" rather than "free". (``Rollout.cost_usd`` is a
        non-optional float that coerces None to 0.0, so "unknown" cannot be expressed in the
        field itself without a core change.)
    """
    global _cost_unpriced_warned

    agent_cost, user_cost = sim.agent_cost, sim.user_cost
    try:
        messages = list(sim.get_messages())
    except Exception:  # noqa: BLE001
        messages = []

    tokens, missing_usage = 0, 0
    try:
        from tau2.utils.llm_utils import get_token_usage

        usage = get_token_usage(messages) or {}
        tokens = int(usage.get("prompt_tokens", 0)) + int(usage.get("completion_tokens", 0))
    except Exception:  # noqa: BLE001
        tokens = 0
    missing_usage = sum(1 for m in messages if getattr(m, "usage", None) is None)

    usersim = _usersim_meta(messages, _user_model())

    if agent_cost is not None or user_cost is not None:
        return (
            float(agent_cost or 0.0) + float(user_cost or 0.0),
            tokens,
            {"cost_source": "tau2", "messages_missing_cost": 0, "messages_missing_usage": missing_usage,
             "usersim": usersim},
        )

    # tau2 gave up on the whole run: salvage whatever the provider did price.
    priced = [m for m in messages if getattr(m, "cost", None) is not None]
    missing = len(messages) - len(priced)
    partial = float(sum(m.cost for m in priced))
    if priced:
        source = "partial_messages"
    else:
        source = "unpriced"
        if not _cost_unpriced_warned:
            _cost_unpriced_warned = True
            print(
                f"tau2: the provider returned no per-message cost (model "
                f"{model_config.MODEL!r}), so eval spend cannot be measured for this run; "
                f"reporting tokens instead. Rollout cost_usd will read 0.0 with "
                f"metadata cost_source='unpriced'.",
                file=sys.stderr,
            )
    return partial, tokens, {
        "cost_source": source,
        "messages_missing_cost": missing,
        "messages_missing_usage": missing_usage,
        "usersim": usersim,
    }


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


def _native_sims_enabled() -> bool:
    """Whether to keep tau2's OWN results.json for this eval (default: yes).

    These are the traces `tau2 view` reads, and reading them is how you learn WHY a
    candidate scored what it scored. A flag you must set to get the feature is a flag
    nobody sets, so the default is ON.
    """
    return str(os.environ.get("CAPEVOLVE_NATIVE_SIMS", "")).strip().lower() not in {
        "0", "false", "no", "off"}

class Adapter(CapabilityAdapter):

    _original_env_ctor = None
    _candidate_fault = None

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """Retail tasks the campaign may evaluate: official TRAIN only (opt + sel). TEST is sealed."""
        allowed = _allowed_ids()
        from tau2.domains.retail.environment import get_tasks as retail_get_tasks

        return [Task(id=str(t.id), input=str(t.id), metadata={"domain": DOMAIN})
                for t in retail_get_tasks(None) if str(t.id) in allowed]

    # ---- running ---------------------------------------------------------

    def _tau2_tasks_by_id(self):
        from tau2.domains.retail.environment import get_tasks as retail_get_tasks

        allowed = _allowed_ids()
        return {str(t.id): t for t in retail_get_tasks(None) if str(t.id) in allowed}

    # ---- tau2's OWN simulation records -----------------------------------
    # ONE path format, byte-identical in EVERY tau2 adapter in this repo (this one, the
    # tau2_custom direct + blackbox arms, and templates/adapters/tau2_bench):
    #
    #     <run_dir>/native_sims/<tag>/<split>/results_<YYYYmmdd_HHMMSS>_<pid>.json
    #
    # Identical on purpose: `tau2 view --dir` takes the same shape whatever arm produced
    # the run, and a trace is attributable without knowing which adapter wrote it. The
    # duplication is deliberate — each adapter ships as ONE self-contained file copied
    # into a project's adapters/, so a shared import would break that.

    def _split_of(self, ctx, task_ids: list[str]) -> str:
        """Which split this batch is, read from the run's own ``splits.json``.

        ``run_batch``/``run_trials`` are not told the split, and the sims of one split
        must not land in another's directory. With a pinned no-holdout split every split
        holds the same ids, so ties resolve in val's favour — val is the split the
        optimizer reads.
        """
        try:
            import json  # noqa: PLC0415

            c = Path(ctx)
            splits = json.loads((c.parent.parent / "splits.json").read_text(encoding="utf-8"))
            want = set(task_ids)
            for name in ("val", "train", "test"):
                ids = {str(i) for i in (splits.get(name) or [])}
                if ids and want <= ids:
                    return name
        except Exception:  # noqa: BLE001 — an unreadable splits.json must not break the eval
            pass
        return "eval"

    def _sim_save_path(self, ctx, split: str):
        """``<run_dir>/native_sims/<tag>/<split>/results_<ts>_<pid>.json``, or ``None``.

        Without a save path tau2 builds ``SimulationResults`` in memory, we convert each
        sim to a ``Rollout``, and the native object is dropped — so `tau2 view` has
        nothing to show even though tau2 closes every run by recommending it.

        The TAG comes free from ``ctx``, the dir the harness passes — under EITHER of the
        two names it uses: ``<run_dir>/candidates/<tag>`` for the baseline and the finalize
        (tag ``seed``, or the winning ``cand_NNNN``), and ``<run_dir>/work/<tag>`` for an
        iteration eval (tag ``cand_0001``). Accepting only ``candidates`` is why candidate
        evals used to write nothing at all — the run dir is ``parent.parent`` either way,
        so one name in the guard is the whole difference. The PHASE ITSELF is not available — no
        argument or env var tells an adapter whether this is the baseline, an iteration or
        the finalize — so ``<split>`` stands in for it: the baseline is the seed on val,
        the finalize is the seed on test.

        WHY the timestamp+pid and not a bare ``results.json``: the same ``<tag>/<split>``
        pair IS written more than once (the seed at baseline and again at finalize), and a
        path tau2 has already written is one it tries to RESUME — it prompts on stdin,
        which an eval does not have. The stamp is unique per (second, process), so there is
        no collision and no suffix walk.

        Returns ``None`` when saving is off or the layout is neither ``candidates/<tag>``
        nor ``work/<tag>`` — native traces are a convenience and must never be the thing
        that breaks a run. tau2 creates the parent dirs itself, so nothing is created here.
        """
        if not _native_sims_enabled():
            return None
        try:
            cand = Path(ctx)
            if cand.parent.name not in ("candidates", "work"):
                return None
            stamp = f"{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
            return (cand.parent.parent / "native_sims" / cand.name / str(split)
                    / f"results_{stamp}.json")
        except Exception:  # noqa: BLE001 — never let an optional artifact break the eval
            return None


    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """Run a batch of retail tasks through tau2's own batch runner.

        Uses the model configured via MODEL env var (see model_config.py).
        """
        from tau2.data_model.simulation import TextRunConfig
        from tau2.runner import run_tasks

        _seal_check([t.id for t in tasks])
        if Adapter._candidate_fault:
            return {t.id: Rollout(task_id=t.id, error="candidate tools fault: " + Adapter._candidate_fault,
                                  metadata={"domain": DOMAIN, "tau2_reward": 0.0, "error_kind": "candidate"}) for t in tasks}
        by_id = self._tau2_tasks_by_id()
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]
        results: dict[str, Rollout] = {}

        for t in tasks:
            if t.id not in by_id:
                results[t.id] = Rollout(
                    task_id=t.id, error=f"task id {t.id} not found in retail task set"
                )
        if not tau2_tasks:
            return results

        max_concurrency = _max_concurrency()

        config = TextRunConfig(
            domain=DOMAIN,
            agent="llm_agent",
            llm_agent=model_config.MODEL,
            llm_args_agent=model_config.llm_kwargs_for("agent"),
            user="user_simulator",
            llm_user=_user_model(),
            llm_args_user=model_config.llm_kwargs_for("user"),
            num_trials=1,
            max_steps=MAX_STEPS,
            max_errors=10,
            # Per-simulation wallclock cap, so ONE wedged rollout cannot block a whole
            # batch (measured: a stuck retail sim ran 40+ min while litellm retried a
            # dropped connection, and rollouts are only persisted once the batch returns).
            # Pair it with a max_concurrency the endpoint can actually sustain: if the
            # provider queues rather than serves, this cap turns starvation into a batch
            # of TIMEOUTs, which _sim_to_rollout now reports as infra rather than as 0.0.
            timeout=float(os.environ.get("TAU2_SIM_TIMEOUT", "1800")),
            max_concurrency=max_concurrency,
            seed=int(seed),
        )

        import contextlib

        with contextlib.redirect_stdout(sys.stderr):
            sim_save = self._sim_save_path(
                ctx, self._split_of(ctx, [t.id for t in tasks]))
            sim_results = run_tasks(
                config,
                tau2_tasks,
                save_path=sim_save,
                console_display=False,
            )
            if sim_save is not None:
                # tau2 closes with a bare "run: tau2 view", which looks in
                # data/simulations and finds nothing — these sims live in the run dir.
                print(f"tau2 view --dir {sim_save.parent}", file=sys.stderr)

        for sim in sim_results.simulations:
            rollout = self._sim_to_rollout(sim)
            results[str(rollout.task_id)] = rollout

        for t in tasks:
            if t.id not in results:
                results[t.id] = Rollout(
                    task_id=t.id,
                    error="no simulation produced for task (tau2 returned nothing)",
                    metadata={"domain": DOMAIN, "tau2_reward": 0.0},
                )
        return results

    @staticmethod
    def _sim_to_rollout(sim) -> Rollout:
        """Map one tau2 SimulationRun to a cap-evolve Rollout.

        See _cost_and_tokens for why cost needs more care than ``sim.agent_cost or 0.0``.
        """
        from tau2.data_model.simulation import TerminationReason

        # TIMEOUT belongs here, and leaving it out silently poisons whole evaluations.
        # Measured: at max_concurrency=300 this litellm proxy queues requests instead of
        # serving them, per-call latency went 20s -> 200s, and 292 of 300 rollouts hit
        # TIMEOUT with a median trace of SIX messages. Because a timed-out sim comes back
        # as an ordinary rollout with reward 0.0, val measured 0.0067 and was reported as
        # the model's capability. A wallclock timeout is a property of the SERVING PATH,
        # not of the policy — the same candidate on a fast endpoint finishes — and tau2
        # already has max_steps for a genuinely looping agent, which ends the sim and
        # scores it normally. So route TIMEOUT into the infra path: score() then calls it
        # "uncontrollable noise, do not optimize against it", the harness stops counting
        # it as a valid trial, coverage drops, and gate.decide REFUSES to judge below
        # min_coverage instead of handing back a confident zero.
        infra_reasons = {
            TerminationReason.INFRASTRUCTURE_ERROR,
            TerminationReason.UNEXPECTED_ERROR,
            TerminationReason.TIMEOUT,
        }

        task_id = str(sim.task_id)
        reward_info = sim.reward_info
        reward = (
            float(reward_info.reward)
            if reward_info is not None and reward_info.reward is not None
            else 0.0
        )
        cost_usd, tokens, cost_meta = _cost_and_tokens(sim)
        term = sim.termination_reason
        error = None
        if term in infra_reasons:
            error = f"tau2 terminated for infrastructure reason: {term}"

        try:
            messages = [m.model_dump() for m in sim.get_messages()]
        except Exception:
            messages = None

        if error is None and reward < 1.0 and _leaked_stop_continuation(messages):
            error = (
                "tau2 user-simulator emitted ###STOP### alongside leaked reasoning that "
                "explicitly planned to continue the conversation (documented artifact, "
                "docs/TAU2_SUMMARY.md row 7) — treated as uncontrollable noise, not an "
                "agent policy/tool failure."
            )

        reward_info_dump = (
            reward_info.model_dump(mode="json") if reward_info is not None else None
        )

        return Rollout(
            task_id=task_id,
            output=messages,
            trace=messages,
            cost_usd=cost_usd,
            tokens=tokens,
            error=error,
            metadata={
                "domain": DOMAIN,
                **({"error_kind": "infra"} if error else {}),
                "judge": {"model": JUDGE_MODEL, "settings": "provider-default (no temperature/max_tokens)",
                          "nl_assertion_verdicts": (reward_info_dump or {}).get("nl_assertions")},
                "tau2_reward": reward,
                "tau2_reward_info": reward_info_dump,
                "termination_reason": str(term),
                **({"infra_detail": _infra_detail(sim, messages)} if term in (TerminationReason.INFRASTRUCTURE_ERROR, TerminationReason.UNEXPECTED_ERROR) else {}),
                **cost_meta,
            },
        )

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int, base_seed: int) -> dict:
        """Run the whole task×trial grid through ONE tau2 run_tasks() call.

        tau2's run_tasks() seeds Python's process-global `random` module once
        (`random.seed(config.seed)` + `random.randint(...)` per trial), single-threaded,
        BEFORE spawning its own internal ThreadPoolExecutor (bounded by
        max_concurrency) to run every (task, trial) pair. That reseed is unsynchronized
        (no lock) and only safe under tau2's intended single-call-per-run usage.

        Calling run_tasks() once per (task, trial) from cap-evolve's OWN external
        thread pool (the previous implementation, via run_trials_pool) invoked that
        unsynchronized reseed concurrently from up to TAU2_MAX_CONCURRENCY threads —
        a race on the shared global RNG state that could scramble which seed a given
        (task, trial) actually got, breaking reproducibility across separate
        evaluations of the same nominal (candidate, base_seed) pair. Making ONE call
        for the whole grid keeps the reseed on the main thread and reuses tau2's own
        (safe) internal concurrency instead.
        """
        from tau2.data_model.simulation import TextRunConfig
        from tau2.runner import run_tasks

        n_trials = max(0, int(n_trials))
        results: dict[str, list[Rollout]] = {t.id: [] for t in tasks}
        if n_trials == 0 or not tasks:
            return results

        _seal_check([t.id for t in tasks])
        if Adapter._candidate_fault:
            return {t.id: [Rollout(task_id=t.id, error="candidate tools fault: " + Adapter._candidate_fault,
                                  metadata={"domain": DOMAIN, "tau2_reward": 0.0, "error_kind": "candidate"}) for _ in range(max(0, int(n_trials)))] for t in tasks}
        by_id = self._tau2_tasks_by_id()
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]
        for t in tasks:
            if t.id not in by_id:
                results[t.id] = [
                    Rollout(task_id=t.id, error=f"task id {t.id} not found in retail task set")
                    for _ in range(n_trials)
                ]
        if not tau2_tasks:
            return results

        max_concurrency = _max_concurrency()

        config = TextRunConfig(
            domain=DOMAIN,
            agent="llm_agent",
            llm_agent=model_config.MODEL,
            llm_args_agent=model_config.llm_kwargs_for("agent"),
            user="user_simulator",
            llm_user=_user_model(),
            llm_args_user=model_config.llm_kwargs_for("user"),
            num_trials=n_trials,
            max_steps=MAX_STEPS,
            max_errors=10,
            # Per-simulation wallclock cap, so ONE wedged rollout cannot block a whole
            # batch (measured: a stuck retail sim ran 40+ min while litellm retried a
            # dropped connection, and rollouts are only persisted once the batch returns).
            # Pair it with a max_concurrency the endpoint can actually sustain: if the
            # provider queues rather than serves, this cap turns starvation into a batch
            # of TIMEOUTs, which _sim_to_rollout now reports as infra rather than as 0.0.
            timeout=float(os.environ.get("TAU2_SIM_TIMEOUT", "1800")),
            max_concurrency=max_concurrency,
            seed=int(base_seed),
        )

        import contextlib

        with contextlib.redirect_stdout(sys.stderr):
            sim_save = self._sim_save_path(
                ctx, self._split_of(ctx, [t.id for t in tasks]))
            sim_results = run_tasks(
                config,
                tau2_tasks,
                save_path=sim_save,
                console_display=False,
            )
            if sim_save is not None:
                # tau2 closes with a bare "run: tau2 view", which looks in
                # data/simulations and finds nothing — these sims live in the run dir.
                print(f"tau2 view --dir {sim_save.parent}", file=sys.stderr)

        by_task_trial: dict[tuple[str, int], Rollout] = {}
        for sim in sim_results.simulations:
            trial = int(sim.trial) if sim.trial is not None else 0
            by_task_trial[(str(sim.task_id), trial)] = self._sim_to_rollout(sim)

        for t in tasks:
            if t.id not in by_id:
                continue
            results[t.id] = [
                by_task_trial.get(
                    (t.id, k),
                    Rollout(
                        task_id=t.id,
                        error="no simulation produced for task/trial (tau2 returned nothing)",
                        metadata={"domain": DOMAIN, "tau2_reward": 0.0},
                    ),
                )
                for k in range(n_trials)
            ]
        return results

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """Run a single task by delegating to run_batch."""
        batch = self.run_batch([task], ctx, seed=seed)
        return batch.get(task.id, Rollout(task_id=task.id, error="no rollout produced"))

    # ---- scoring ---------------------------------------------------------

    def score(self, task: Task, rollout: Rollout) -> Score:
        """Score a rollout with tau2's own reward; gold-SAFE feedback."""
        meta = rollout.metadata or {}

        if rollout.error:
            return Score(
                task_id=task.id,
                reward=0.0,
                feedback=(
                    "Rollout did not complete for an infrastructure reason "
                    f"({rollout.error}). This is uncontrollable noise, not an agent "
                    "policy/tool failure; do not optimize against it."
                ),
            )

        reward = float(meta.get("tau2_reward", 0.0) or 0.0)
        reward_info = meta.get("tau2_reward_info") or {}
        # The localizers read the agent's OWN tool calls out of meta["trace"], but this
        # adapter keeps the trace on Rollout.trace — so pass an enriched view. Without it
        # every _localize_* call raised and the feedback silently degraded to the
        # tool-name-only fallback ("right tool, right arguments"), which is exactly the
        # signal an optimizer cannot act on.
        signal_meta = {**meta, "trace": rollout.trace or [],
                       "tool_calls": getattr(rollout, "tool_calls", None) or []}
        feedback = self._build_feedback(reward, reward_info, signal_meta)
        return Score(task_id=task.id, reward=reward, feedback=feedback)

    @classmethod
    def _build_feedback(cls, reward: float, reward_info: dict, meta: dict) -> str:
        """Argument-level, gold-SAFE learning signal.

        For each failing check we localize the defect: name the wrong ARGUMENT key +
        the AGENT'S OWN wrong value (never the gold value), the wrong target id, and
        — for communicate misses — the un-stated computed value when derivable from
        the agent's own state. A tool-name-only signal is too coarse for the optimizer
        to localize a fix. Falls back to the tool-name message when a piece cannot be
        safely derived. Deterministic on a fixed rollout.
        """
        basis = [str(b).upper() for b in (reward_info.get("reward_basis") or [])]
        if not basis:
            basis = [k.upper() for k in (reward_info.get("reward_breakdown") or {})]
        if not reward_info:
            if reward >= 1.0:
                return "Task fully solved (reward 1.0)."
            return (
                f"Task scored {reward:.3f}. No detailed check breakdown is available "
                "for this rollout."
            )

        facts = cls._user_profile_facts(meta)
        lines: list[str] = [f"Task reward: {reward:.3f}."]

        # A premature termination leaves EVERY check null, so without this the feedback is the
        # bare "Task reward: 0.000." and nothing else - a zero with no stated cause, which is the
        # least actionable signal this adapter can emit. tau2 records the reason in
        # reward_info["info"]["note"]; surface it and say plainly that the rollout is not evidence
        # about the policy or the tools. Measured: 1 of 170 failures, cause "max_steps".
        note = ((reward_info.get("info") or {}) or {}).get("note")
        if note and not reward_info.get("db_check") and not reward_info.get("reward_basis"):
            lines.append(
                f"The rollout did not complete: {note} Every graded check is therefore null, so "
                "this zero says nothing about the policy or the tools - do not optimise against "
                "it. If it recurs on one task, that task needs more steps or a shorter path, not "
                "a different edit."
            )
            return " ".join(lines)

        # DB check (final environment state matches expectation). The sentence is emitted
        # LATER, once we know whether per-action detail actually follows it: it used to promise
        # "See the per-action detail below" unconditionally, and on a DB-only divergence no
        # detail follows at all. Task 10 failed 11 times with that exact feedback and nothing
        # after it, which tells an optimiser to go looking for a wrong argument that does not
        # exist. A pointer to absent evidence is worse than no pointer.
        db_check = reward_info.get("db_check")
        db_mismatch = db_check is not None and not db_check.get("db_match", True)


        # Action checks: localize each failed action at the ARGUMENT level.
        action_checks = reward_info.get("action_checks") or []
        details: list[str] = []
        for ac in action_checks:
            if ac.get("action_match", True):
                continue
            action = ac.get("action") or {}
            name = action.get("name") or action.get("func_name") or "an action"
            # KEYS that matter (names only — gold-safe). Prefer compare_args; else the
            # gold arg keys (keys, not values). Values are never read.
            gold_keys = action.get("compare_args")
            if not gold_keys:
                gold_args = action.get("arguments")
                gold_keys = sorted(gold_args.keys()) if isinstance(gold_args, dict) else []
            try:
                details.append(cls._localize_action(str(name), list(gold_keys or []), meta, facts))
            except Exception:
                details.append(f"{name}: not performed correctly (right tool, right arguments)")
        details = cls._collapse_action_details(details, meta)

        if db_mismatch:
            if details:
                lines.append(
                    "Database state does NOT match the expected final state — a required write "
                    "(book/update/cancel) was missing, wrong, or extra. See the per-action "
                    "detail below for the specific wrong argument."
                )
            else:
                # No gold action mismatched, yet the DB differs. So the divergence is not a
                # wrong VALUE: it is an extra or duplicated write, or a side effect of a write
                # (notably `payment_history`, which every successful update appends to and which
                # no retry removes). Naming the agent's OWN writes is gold-safe and is the only
                # actionable evidence available here.
                writes = [
                    f"{n}({', '.join(f'{k}={v!r}' for k, v in sorted(a.items()) if k in ('order_id', 'item_ids', 'new_item_ids', 'payment_method_id', 'reason'))})"
                    for n, a in cls._iter_agent_tool_calls(meta)
                    if n in ("cancel_pending_order", "exchange_delivered_order_items", "modify_pending_order_address",
                             "modify_pending_order_items", "modify_pending_order_payment",
                             "modify_user_address", "return_delivered_order_items")
                ]
                msg = (
                    "Database state does NOT match the expected final state, but NO gold action "
                    "mismatched — so this is not a wrong argument value. The divergence is an "
                    "EXTRA or DUPLICATED write, or a write side effect: every successful update "
                    "appends a charge to `payment_history`, and re-issuing a corrected write "
                    "does not undo the first one. "
                )
                if writes:
                    msg += (f"The {len(writes)} write(s) you performed, in order: "
                            + "; ".join(writes) + ". Check whether one of them should not have "
                            "happened at all, or happened twice.")
                else:
                    msg += ("You performed NO writes at all, so a required write is simply "
                            "missing.")
                lines.append(msg)

        if details:
            # Only SOME components gate a task's reward. tau2 publishes that as
            # `reward_basis`, and on this benchmark it is routinely ["DB", "COMMUNICATE"] with
            # ACTION absent - meaning action checks cannot change the score at all. The
            # feedback used to lead with "Action-level defects" regardless, which points an
            # optimiser at read calls that provably do not matter: task 12 reports
            # "calculate: was never called" on every rollout, `calculate` was invoked in 0 of
            # 300 rollouts, and the task still scores 0.8. Say which components actually gate,
            # and label non-gating detail as diagnostic so nobody spends a round on it.
            if "ACTION" in basis:
                lines.append("Action-level defects (your own wrong values): "
                             + "; ".join(details) + ".")
            else:
                lines.append("Action-trace detail (DIAGNOSTIC ONLY - this task is scored on "
                             + "/".join(basis or ["DB"]) + ", so action checks do NOT affect "
                             "your reward; use these only as a clue to the wrong write): "
                             + "; ".join(details) + ".")

        # Communicate checks: name the un-stated derivable value when possible.
        communicate_checks = reward_info.get("communicate_checks") or []
        missed_comm = [c for c in communicate_checks if not c.get("met", True)]
        if missed_comm:
            comm_details: list[str] = []
            for c in missed_comm:
                try:
                    d = cls._localize_communicate(c, meta, facts)
                except Exception:
                    d = None
                if d:
                    comm_details.append(d)
            if comm_details:
                lines.append("Communication misses: " + "; ".join(comm_details) + ".")
            else:
                lines.append(
                    f"{len(missed_comm)} required piece(s) of information were not clearly "
                    "communicated to the user. State the confirmations/details (e.g. the "
                    "computed total, the new flight times) the policy requires you to convey."
                )

        # NL assertions.
        nl_assertions = reward_info.get("nl_assertions") or []
        missed_nl = [n for n in nl_assertions if not n.get("met", True)]
        if missed_nl:
            lines.append(
                f"{len(missed_nl)} behavioral expectation(s) were not met. Re-check the "
                "policy steps for this scenario."
            )

        # Env assertions.
        env_assertions = reward_info.get("env_assertions") or []
        missed_env = [e for e in env_assertions if not e.get("met", True)]
        if missed_env:
            lines.append(
                f"{len(missed_env)} environment assertion(s) failed (the resulting "
                "system state was not as required)."
            )

        if reward >= 1.0 and len(lines) == 1:
            lines.append("All checks passed.")

        return " ".join(lines)

    # ---- making a candidate live ----------------------------------------

    @staticmethod
    def _iter_agent_tool_calls(meta: dict):
        """Yield (tool_name, arguments) for every ASSISTANT tool call in the trace.

        Pure read of the agent's own messages. Deterministic order (trace order).
        """
        for msg in meta.get("trace") or []:
            if not isinstance(msg, dict):
                continue
            if msg.get("role") != "assistant":
                continue
            for tc in msg.get("tool_calls") or []:
                if not isinstance(tc, dict):
                    continue
                name = tc.get("name")
                args = tc.get("arguments") or {}
                if name:
                    yield str(name), (args if isinstance(args, dict) else {})

    @staticmethod
    def _user_profile_facts(meta: dict) -> dict:
        """Derive what the AGENT observed about the user's own profile/state.

        Reads only ``get_user_details``/``get_reservation_details`` TOOL RESULTS in
        the trace (the agent's own observations — gold-safe). Returns:
          {"payment_methods": [...ids...], "reservation_ids": [...ids...]}
        Best-effort and deterministic; returns empty lists when nothing is parseable.
        """
        import json
        import re

        payment_ids: list[str] = []
        reservation_ids: list[str] = []
        seen_p: set[str] = set()
        seen_r: set[str] = set()

        for msg in meta.get("trace") or []:
            if not isinstance(msg, dict) or msg.get("role") != "tool":
                continue
            content = msg.get("content")
            if not isinstance(content, str) or not content:
                continue
            obj = None
            try:
                obj = json.loads(content)
            except Exception:
                obj = None

            if isinstance(obj, dict):
                pm = obj.get("payment_methods")
                if isinstance(pm, dict):
                    for pid in pm.keys():
                        if pid not in seen_p:
                            seen_p.add(pid)
                            payment_ids.append(str(pid))
                elif isinstance(pm, list):
                    for entry in pm:
                        pid = entry.get("id") if isinstance(entry, dict) else None
                        if pid and pid not in seen_p:
                            seen_p.add(pid)
                            payment_ids.append(str(pid))
                # Only STRING elements are ids. A candidate is free to enrich this tool's
                # return with reservation summary objects, and str()-ing those produced a
                # held=[{...}, {...}] blob that read like "your id is not among the user's
                # reservations" for calls whose id was perfectly valid — which sent one
                # optimiser chasing a scoring bug that did not exist (reward comes from
                # tau2's own checks and never reads this field; only THIS feedback string
                # does). Ids also get collected from dict/objects under any key below.
                res = obj.get("reservations")
                if isinstance(res, list):
                    for entry in res:
                        rid = entry if isinstance(entry, str) else (
                            entry.get("reservation_id") or entry.get("id")
                            if isinstance(entry, dict) else None
                        )
                        if rid and str(rid) not in seen_r:
                            seen_r.add(str(rid))
                            reservation_ids.append(str(rid))
                rid = obj.get("reservation_id")
                if rid and str(rid) not in seen_r:
                    seen_r.add(str(rid))
                    reservation_ids.append(str(rid))
            else:
                # Fall back to regex over the raw text for known id shapes.
                for pid in re.findall(r"\b(?:credit_card|gift_card|certificate)_\d+\b", content):
                    if pid not in seen_p:
                        seen_p.add(pid)
                        payment_ids.append(pid)

        return {"payment_methods": payment_ids, "reservation_ids": reservation_ids}

    @classmethod
    def _collapse_action_details(cls, details: list[str], meta: dict) -> list[str]:
        """Collapse repeated per-gold-action lines into one COUNTED line per tool.

        ``_localize_action`` runs once per failed gold action and always reports the agent's
        last call of that tool, so N failed gold actions of the same tool produced N IDENTICAL
        strings. On task 42 the feedback read
        ``get_reservation_details: agent used reservation_id='FDZ0T5'`` seven times and
        ``cancel_reservation: agent used reservation_id='HSR97W'`` twice, which tells an
        optimiser nothing and reads like a stutter in the harness.

        What those repeats actually encode is a COUNT — gold performed that tool 7 and 2 times —
        and the useful comparison is against how many times the agent called it, plus the
        distinct arguments it used. That is gold-safe: it reveals how many calls were expected,
        never which ones were right. On task 42 it turns an unreadable line into
        ``cancel_reservation: gold performs this 2x, you called it 4x (SE9KEL, FDZ0T5, PUNERT,
        HSR97W) - you are cancelling too many``, which names the defect directly.
        """
        from collections import Counter, OrderedDict

        counts = Counter(details)
        agent_counts: Counter = Counter()
        agent_args: dict[str, list[str]] = {}
        for n, args in cls._iter_agent_tool_calls(meta):
            agent_counts[n] += 1
            if isinstance(args, dict):
                for k, v in args.items():
                    kl = k.lower()
                    # user_id ends in _id but names the CALLER, not the target the agent chose;
                    # including it put the customer's own id in every "wrong subset" list.
                    if kl in ("user_id", "userid"):
                        continue
                    if "reservation" in kl or kl.endswith("_id"):
                        agent_args.setdefault(n, [])
                        if str(v) not in agent_args[n]:
                            agent_args[n].append(str(v))
        out: "OrderedDict[str, str]" = OrderedDict()
        for line, n_gold in counts.items():
            tool = line.split(":", 1)[0].strip()
            if n_gold == 1:
                out[line] = line
                continue
            n_agent = agent_counts.get(tool, 0)
            seen = agent_args.get(tool) or []
            shown = ", ".join(seen[:8]) + ("..." if len(seen) > 8 else "")
            msg = (f"{tool}: gold performs this {n_gold}x, you called it {n_agent}x"
                   + (f" ({shown})" if shown else ""))
            if n_agent > n_gold:
                msg += " - you are calling it too many times, on the wrong subset"
            elif n_agent < n_gold:
                msg += " - you stopped before making all the required calls"
            out[msg] = msg
        return list(out)

    @classmethod
    def _localize_action(cls, gold_name: str, gold_keys: list[str], meta: dict, facts: dict) -> str:
        """Argument-level, gold-SAFE detail for one failed action check.

        ``gold_keys`` are the argument KEYS that matter (names only — gold-safe).
        We report the AGENT'S OWN value for those keys from its own call(s) of
        ``gold_name``; we never read or print the gold values. For id-shaped keys
        we surface what was AVAILABLE on the user's own profile/state.
        """
        agent_calls = [args for (n, args) in cls._iter_agent_tool_calls(meta) if n == gold_name]
        if not agent_calls:
            return f"{gold_name}: was never called (or not called correctly)"

        keys = gold_keys or sorted({k for c in agent_calls for k in c.keys()})
        # Use the LAST call of the tool (the state the agent settled on); deterministic.
        used = agent_calls[-1]
        parts: list[str] = []
        for k in keys:
            v = used.get(k, "<missing>")
            detail = f"{k}={v!r}"
            kl = k.lower()
            if "payment" in kl and facts.get("payment_methods"):
                avail = facts["payment_methods"]
                if v not in avail:
                    detail += f" (not on the user's profile; available={avail})"
            elif ("reservation" in kl or kl in {"reservation_id", "target", "res_id"}) and facts.get(
                "reservation_ids"
            ):
                avail = facts["reservation_ids"]
                if v not in avail:
                    detail += f" (not among the user's reservations; held={avail})"
            parts.append(detail)
        return f"{gold_name}: agent used " + ", ".join(parts)

    @classmethod
    def _localize_communicate(cls, check: dict, meta: dict, facts: dict) -> str | None:
        """Name a derivable un-stated value for a missed communicate check (gold-safe).

        We only surface a concrete value the agent could have computed from its OWN
        observed state (e.g. a total cost summed from the user's observed payment/
        reservation data). The check's ``info`` text may embed the gold answer, so we
        DO NOT echo it verbatim — we classify the topic and, when a total is derivable,
        name the computed value. Returns None when nothing is safely derivable.
        """
        raw_info = str(check.get("info") or "")
        info = raw_info.lower()
        stated = cls._numbers_the_agent_stated(meta)

        # A communicate check's `info` is frequently the REQUIRED VALUE ITSELF (tau2 retail
        # stores e.g. "1628"), so it must never be echoed. But its SHAPE is safe to use, and
        # it is the difference between an actionable message and the useless generic one:
        # "you never said a figure" and "you said a figure and it was wrong" need different
        # edits. Reporting the agent's OWN numbers back is gold-safe; the required value is
        # never printed, and the only thing revealed is what the agent already knows it said.
        required_is_a_number = bool(re.fullmatch(r"[0-9][0-9,]*(?:\.[0-9]{1,2})?", raw_info.strip()))
        if required_is_a_number:
            try:
                want = float(raw_info.strip().replace(",", ""))
            except ValueError:
                want = None
            # Truncating this list is not cosmetic: an optimiser that has already stated the
            # right figure reads a 5-item excerpt as "it is not in there" and goes on guessing.
            # Show them all, and say how many, so absence is absence.
            shown = ", ".join(f"{v:,.2f}" for v in stated[:40])
            if len(stated) > 40:
                shown += f" (+{len(stated) - 40} more)"
            shown = f"{len(stated)} distinct figures: {shown}"
            if want is not None and any(abs(v - want) < 0.005 for v in stated):
                return ("stated the required figure but the check still did not match it — a "
                        "FORMATTING problem, not an arithmetic one. State the number plainly "
                        "in its own sentence (digits, standard thousands separator, no ranges "
                        "or approximations around it) rather than embedded in a table or list.")
            if stated:
                return ("a specific required figure was never stated. You DID state "
                        f"{shown} — so the miss is in the ARITHMETIC or in WHICH ITEMS you "
                        "included, not in whether you spoke. Re-check the scope: which "
                        "reservations/segments belong in this figure, and justify every "
                        "exclusion against what the user asked for.")
            return ("a specific required figure was never stated. Compute it from the amounts "
                    "you already observed and state it plainly in its own sentence.")

        if "total" in info and ("cost" in info or "price" in info or "$" in info):
            # NOTE: this used to call a `_derive_total_cost` helper that does not exist on
            # this class. The AttributeError was swallowed by the caller's bare `except`, so
            # EVERY failed total-cost check degraded to the generic "1 required piece(s) of
            # information were not clearly communicated" — the least actionable string in the
            # signal. Never let a feedback helper fail silently.
            derive = getattr(cls, "_derive_total_cost", None)
            total = derive(meta) if callable(derive) else None
            if stated:
                shown = ", ".join(f"${v:,.2f}" for v in stated[:40])
                return ("stated a total that did not match the required value. You DID state "
                        f"a computed figure ({shown}) — the miss is in the ARITHMETIC or in "
                        "which items you included, not in whether you spoke.")
            if total is not None:
                return ("did not state the computed total cost (derivable from your own "
                        f"observed amounts: ${total:.2f})")
            return ("did not state the computed total cost (sum the amounts you already "
                    "observed and state it)")
        return None

    def apply(self, candidate_dir, edits=None) -> None:
        """Make candidate_dir the live retail capability (policy + tools) FOR THE AGENT ONLY.

        The evaluator (DB-hash check, which replays gold actions and the agent's tool calls) always
        gets the PRISTINE environment: ``evaluate_simulation`` is wrapped so the thread-local
        ``pristine`` flag makes the candidate constructor return the original one. Candidate tools
        therefore cannot move the gold side. The NL-assertion judge is repointed at the campaign
        gateway (tau2's default gpt-4.1 is not available there)."""
        if edits:
            self.materialize(candidate_dir, edits)

        candidate_dir = _surface_lock(Path(candidate_dir))

        from tau2.environment.environment import Environment
        from tau2.registry import registry

        if Adapter._original_env_ctor is None:
            Adapter._original_env_ctor = registry._domains.get(DOMAIN)
        orig_ctor = Adapter._original_env_ctor
        registry._domains[DOMAIN] = orig_ctor

        import tau2.evaluator.evaluator_nl_assertions as _nl
        import tau2.runner.simulation as _rs

        _nl.DEFAULT_LLM_NL_ASSERTIONS = JUDGE_MODEL
        _nl.DEFAULT_LLM_NL_ASSERTIONS_ARGS = {k: v for k, v in _kwargs("judge").items()}
        if not getattr(_rs, "_capevolve_pristine_eval", False):
            _orig_eval = _rs.evaluate_simulation

            def _eval_pristine(*a, **k):
                _PRISTINE.on = True
                try:
                    return _orig_eval(*a, **k)
                finally:
                    _PRISTINE.on = False

            _rs.evaluate_simulation = _eval_pristine
            _rs._capevolve_pristine_eval = True

        policy_text = _read_candidate_policy(candidate_dir)
        # E05: a candidate whose tools code cannot be imported/constructed/enumerated is a CANDIDATE fault
        # (scored 0 under errored_trial_policy=fail), not missing data. Checked once per apply, no model calls.
        Adapter._candidate_fault = None
        try:
            _tk = _build_candidate_tools(candidate_dir)
            _tk.get_tools()
            if not getattr(_tk, "tools", None) and not _tk.get_tools():
                raise RuntimeError("candidate toolkit exposes no tools")
        except BaseException as exc:  # noqa: BLE001 - includes SyntaxError/ImportError from exec_module
            Adapter._candidate_fault = f"{type(exc).__name__}: {exc}"[:500]

        def candidate_get_environment(db=None, solo_mode: bool = False):
            if getattr(_PRISTINE, "on", False):
                return orig_ctor(db=db, solo_mode=solo_mode)
            if solo_mode:
                raise ValueError("Retail domain does not support solo mode")
            tools = _build_candidate_tools(candidate_dir)
            return Environment(
                domain_name=DOMAIN,
                policy=policy_text,
                tools=tools,
            )

        registry._domains[DOMAIN] = candidate_get_environment



def _surface_lock(candidate_dir: Path) -> Path:
    """Suite D surface lock. TAU_SURFACES = policy | tools | policy,tools (default: no lock). Files of a LOCKED surface are read
    from the pristine seed (TAU_SEED_DIR), never from the candidate; every distinct candidate that differs from the seed on a locked
    surface is recorded in TAU_VIOLATION_FILE (surface_violations.json). Returns the directory the agent environment is built from."""
    import hashlib, json as _j, shutil, tempfile
    spec = {x.strip() for x in os.environ.get("TAU_SURFACES", "policy,tools").split(",") if x.strip()}
    if spec >= {"policy", "tools"}:
        return candidate_dir
    seed = Path(os.environ["TAU_SEED_DIR"])
    files = {"policy": "policy/policy.md", "tools": "tools/tools.py"}
    locked = [k for k in files if k not in spec]
    viol = [k for k in locked if (candidate_dir / files[k]).exists() and (candidate_dir / files[k]).read_bytes() != (seed / files[k]).read_bytes()]
    h = hashlib.sha256()
    for k in files:
        p = candidate_dir / files[k]
        h.update(p.read_bytes() if p.exists() else b"")
    key = h.hexdigest()[:16]
    vf = os.environ.get("TAU_VIOLATION_FILE")
    if vf and viol:
        p = Path(vf)
        try:
            d = _j.loads(p.read_text()) if p.exists() else {"violating_candidates": {}, "n_violating_candidates": 0}
            d["violating_candidates"][key] = {"surfaces": viol, "candidate_dir": str(candidate_dir)}
            d["n_violating_candidates"] = len(d["violating_candidates"])
            p.write_text(_j.dumps(d, indent=1))
        except Exception:  # noqa: BLE001
            pass
    eff = Path(tempfile.mkdtemp(prefix="surflock_")) / "cand"
    shutil.copytree(candidate_dir, eff)
    for k in locked:
        dst = eff / files[k]; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy(seed / files[k], dst)
    return eff

_PRISTINE = _threading.local()
