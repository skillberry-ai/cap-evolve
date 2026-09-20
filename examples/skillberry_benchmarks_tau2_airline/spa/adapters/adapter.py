"""Project adapter — optimize tau2-bench AIRLINE's TOOL SURFACE, delivered via SPA.

The capability is the airline agent's TOOLS ONLY. tau2's system prompt (the airline
policy) is NOT part of it and is never edited: under this intervention the policy reaches
the agent unchanged (SPA keeps the request's system messages, ``USE_AGENT_PROMPTS=true``)
while the agent's TOOLS come from the Skillberry Store skill the proxy serves.

  * ``tasks``        -> all 50 tau2 airline tasks (stable, network-free).
  * ``run_trials``   -> ONE ``tau2.run.run_tasks`` call for the whole task x trial grid
                        (the fast path cap-evolve prefers), grouped by ``sim.trial``.
  * ``run_batch``    -> the same call with ``num_trials=1`` (one cap-evolve trial).
  * ``score``        -> tau2's OWN reward (``sim.reward_info.reward``), read from what the
                        run stashed — never re-run, so it is deterministic. Feedback is
                        gold-AWARE but gold-SAFE and ARGUMENT-LEVEL.
  * ``apply``        -> deploys the candidate as THE store skill and restarts SPA onto it.
                        Guarded on the CANDIDATE'S SHAPE, and it NEVER raises.
  * ``trajectories`` -> the dir of tau2's native per-eval results (full transcript +
                        reward_info), under the run dir.

Nothing here touches the network at import time, so ``cap-evolve check`` stays offline.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

# Sibling helper modules (gateway.py) importable regardless of the caller's cwd.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap_evolve import CapabilityAdapter, Rollout, Score, Task

import gateway
from scoring import Tau2ScoringMixin   # sibling module, see scoring.py

# --- the SPA intervention ---------------------------------------------------------
# The skill name is fixed by convention and is ALSO the store's delete key and the name
# SPA is started with: the single sub-package under capability_path IS the store name, so
# nothing can disagree about it.
SKILL_NAME = "my_skill"
FROZEN_DIR = "primitive_tools"
FROZEN_MODULE = "functions.py"
# The tag that marks the frozen substrate, so a skill redeploy cannot cascade into it.
FROZEN_TAG = "tau2-airline-primitives"
N_PRIMITIVES = 14

DOMAIN = "airline_skillberry"     # tau2's SPA-aware airline domain (env fronted over HTTP)


def _native_sims_enabled() -> bool:
    """Whether to keep tau2's OWN results.json for this eval (default: yes).

    These are the traces `tau2 view` reads, and reading them is how you learn WHY a
    candidate scored what it scored. A flag you must set to get the feature is a flag
    nobody sets, so the default is ON.
    """
    return str(os.environ.get("CAPEVOLVE_NATIVE_SIMS", "")).strip().lower() not in {
        "0", "false", "no", "off"}


def _spa_env():
    """Import the SPA intervention's library from the skills tree. Lazy: no import-time
    cost for ``check``, and the path is resolved from this project's location."""
    root = Path(__file__).resolve().parents[3]      # <repo>/.capevolve/project/adapters
    scripts = root / "skills" / "interventions" / "llm-proxies" / "spa" / "scripts"
    if not (scripts / "spa_env.py").exists():
        raise RuntimeError(f"SPA intervention library not found at {scripts}")
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import spa_env  # noqa: PLC0415

    return spa_env


class Adapter(Tau2ScoringMixin, CapabilityAdapter):

    # The shared scoring mixin stamps this into rollout metadata; it differs per
    # arm, so it is bound here rather than in scoring.py.
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        self._deploy_error: str | None = None
        self._traj_dirs: dict[str, Path] = {}

    # ---- tasks -----------------------------------------------------------

    def tasks(self, split: str) -> list[Task]:
        """ALL 50 tau2 airline tasks for any split (the harness filters by pinned ids).

        Network-free: ``get_tasks`` reads tau2's own task file. Deliberately NOT the
        domain's environment constructor, which would POST to the environment service.
        """
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        return [Task(id=str(t.id), input=str(t.id), metadata={"domain": DOMAIN})
                for t in airline_get_tasks()]

    def _tau2_tasks_by_id(self) -> dict:
        from tau2.domains.airline.environment import get_tasks as airline_get_tasks

        return {str(t.id): t for t in airline_get_tasks()}

    def runner_model(self) -> str | None:
        """The CONSUMING model: what SPA actually calls upstream for the agent."""
        gateway.load_env()
        m = os.environ.get("SPA_MODEL_NAME") or gateway.DEFAULT_GATEWAY_MODEL
        # Strip the litellm route + vendor prefixes so the id resolves to a capability
        # tier rather than looking like an unknown model.
        return m.split("/")[-1]

    # ---- trajectories ----------------------------------------------------

    # ---- tau2's OWN simulation records -----------------------------------
    # ONE path format, byte-identical in EVERY tau2 adapter in this repo (this one, the
    # skillberry_benchmarks direct + spa arms, and templates/adapters/tau2_bench):
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


    def _errored(self, tasks: list[Task], why: str, n: int) -> dict:
        return {t.id: [Rollout(task_id=t.id, error=why) for _ in range(n)] for t in tasks}

    def run_trials(self, tasks: list[Task], ctx, *, n_trials: int,
                   base_seed: int) -> dict[str, list[Rollout]]:
        """Run the WHOLE task x trial grid in ONE tau2 ``run_tasks`` call.

        cap-evolve calls this once per candidate instead of looping ``run_batch`` per
        trial; per-trial persistence downstream is unchanged, so pass^k / SE / resume keep
        working. Returns ``{task_id: [t0, t1, ...]}`` in trial order.
        """
        n_trials = max(1, int(n_trials))
        if self._deploy_error:
            # A failed deployment is infrastructure noise, not a verdict on the
            # capability: erroring the rollouts makes the harness EXCLUDE this candidate
            # instead of scoring it 0.0.
            return self._errored(tasks, f"SPA deploy failed: {self._deploy_error}", n_trials)

        by_id = self._tau2_tasks_by_id()
        results: dict[str, list[Rollout]] = {t.id: [None] * n_trials for t in tasks}
        for t in tasks:
            if t.id not in by_id:
                results[t.id] = [Rollout(task_id=t.id, error=f"task id {t.id} not in the "
                                         "airline task set") for _ in range(n_trials)]
        tau2_tasks = [by_id[t.id] for t in tasks if t.id in by_id]
        if not tau2_tasks:
            return results

        split = self._split_of(ctx, [t.id for t in tasks])
        # None => tau2 builds SimulationResults in memory only; _sim_to_rollout still gets
        # every sim, so the rollouts and the score are IDENTICAL either way. Registering the
        # parent is what makes trajectories() able to hand this dir to the optimizer.
        save_to = self._sim_save_path(ctx, split)
        if save_to is not None:
            self._traj_dirs[split] = save_to.parent

        agent_m, user_m = gateway.agent_model(), gateway.user_model()
        # Validates the gateway credentials at CONFIG time (loudly) rather than as a wall
        # of 401s that would read as a bad capability.
        user_args = gateway.upstream_llm_args()
        gateway.register_zero_cost(agent_m, user_m)
        # Every agent call funnels through ONE proxy and ONE store process, so the default
        # is deliberately low here (the direct arm runs at 125).
        max_concurrency = int(os.environ.get("TAU2_MAX_CONCURRENCY", "4"))

        import contextlib

        from tau2.run import run_tasks

        # tau2 reconfigures loguru to print() and reports progress on STDOUT; the skills'
        # stdout is a pure-JSON contract, so tau2's goes to stderr for the duration.
        with contextlib.redirect_stdout(sys.stderr):
            sim_results = run_tasks(
                domain=DOMAIN,
                tasks=tau2_tasks,
                agent="llm_agent",
                user="user_simulator",
                llm_agent=agent_m,
                llm_args_agent=gateway.agent_llm_args(),
                llm_user=user_m,
                llm_args_user=user_args,
                num_trials=n_trials,
                max_steps=100,
                max_errors=10,
                max_concurrency=max_concurrency,
                seed=int(base_seed),
                save_to=save_to,
                console_display=False,
                log_level=os.environ.get("TAU2_LOG_LEVEL", "WARNING"),
            )
            if save_to is not None:
                # tau2 closes with a bare "run: tau2 view", which looks in
                # data/simulations and finds nothing — these sims live in the run dir.
                print(f"tau2 view --dir {save_to.parent}", file=sys.stderr)

        for sim in sim_results.simulations:
            slot = results.setdefault(str(sim.task_id), [None] * n_trials)
            trial = int(getattr(sim, "trial", 0) or 0)
            if 0 <= trial < n_trials:
                slot[trial] = self._sim_to_rollout(sim)
        return results

    def run_batch(self, tasks: list[Task], ctx, *, seed: int = 0) -> dict:
        """One cap-evolve trial: ``run_trials`` with ``n_trials=1``."""
        batch = self.run_trials(tasks, ctx, n_trials=1, base_seed=int(seed))
        out: dict[str, Rollout] = {}
        for t in tasks:
            trials = batch.get(t.id) or []
            out[t.id] = trials[0] if trials and trials[0] is not None else Rollout(
                task_id=t.id, error="no simulation produced for task (tau2 returned nothing)")
        return out

    def run_target(self, task: Task, ctx, *, seed: int = 0) -> Rollout:
        """One task, via ``run_batch`` (the base contract requires this method)."""
        return self.run_batch([task], ctx, seed=seed).get(
            task.id, Rollout(task_id=task.id, error="no rollout produced"))

    # ---- the one per-arm hook the shared feedback stack calls -------------
    @staticmethod
    def _user_profile_facts(meta: dict) -> dict:
        """What the AGENT ITSELF observed about the user's own state (gold-safe).

        Parsed from the agent's own ``get_user_details`` / ``get_reservation_details``
        tool RESULTS, so the feedback can say what WAS available without reading gold.
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
            try:
                obj = json.loads(content)
            except Exception:  # noqa: BLE001
                obj = None
            if isinstance(obj, dict):
                pm = obj.get("payment_methods")
                ids = (list(pm.keys()) if isinstance(pm, dict)
                       else [e.get("id") for e in pm if isinstance(e, dict)]
                       if isinstance(pm, list) else [])
                for pid in ids:
                    if pid and str(pid) not in seen_p:
                        seen_p.add(str(pid))
                        payment_ids.append(str(pid))
                res = obj.get("reservations")
                if isinstance(res, list):
                    for rid in res:
                        if str(rid) not in seen_r:
                            seen_r.add(str(rid))
                            reservation_ids.append(str(rid))
                rid = obj.get("reservation_id")
                if rid and str(rid) not in seen_r:
                    seen_r.add(str(rid))
                    reservation_ids.append(str(rid))
            else:
                for pid in re.findall(r"\b(?:credit_card|gift_card|certificate)_\d+\b", content):
                    if pid not in seen_p:
                        seen_p.add(pid)
                        payment_ids.append(pid)
        return {"payment_methods": payment_ids, "reservation_ids": reservation_ids}
    def apply(self, candidate_dir, edits=None) -> None:
        """Deploy ``candidate_dir`` as THE skill the store serves, and restart SPA onto it.

        Guarded on the CANDIDATE'S SHAPE (is a skill package present?), not on the spec:
        a spec/seed mismatch then fails loudly here instead of silently delivering the
        candidate the other way.

        NEVER raises. cap-evolve enters ``live()`` inline, so an exception would abort the
        whole run over one flaky restart; instead the failure is recorded and the rollouts
        come back errored, which makes the harness EXCLUDE the candidate rather than score
        it 0.0 — correct, because a failed deployment is infra noise, not a verdict.
        """
        if edits:
            self.materialize(candidate_dir, edits)
        self._deploy_error = None          # never inherit the previous candidate's

        cdir = Path(candidate_dir)
        skill_dir = cdir / SKILL_NAME
        frozen = cdir / FROZEN_DIR / FROZEN_MODULE
        if not (skill_dir / "SKILL.md").exists():
            self._deploy_error = (
                f"{SKILL_NAME}/SKILL.md missing under {cdir} — this project is wired for the "
                "SPA intervention, whose candidate is ONE skill package. A candidate in the "
                "direct shape (policy/ + tools/) means the spec and the seed disagree.")
            return
        if not frozen.exists():
            self._deploy_error = f"frozen primitives module missing at {frozen}"
            return

        try:
            spa = _spa_env()
            protect = spa.Protection(tags=(FROZEN_TAG,))
            # Self-heal a store that has no substrate (e.g. a cold start): the frozen
            # module is byte-identical in every candidate, so importing it from here is
            # the same substrate the onboarding registered, and Protection keeps it
            # across every later redeploy.
            if len(protect.present_names()) < N_PRIMITIVES:
                spa.import_standalone_tools(frozen, tags=(FROZEN_TAG,))
            spa.reset_store_to_skill(skill_dir, SKILL_NAME, protect)   # primitives first, skill second
            spa.restart_spa(SKILL_NAME)
        except Exception as e:  # noqa: BLE001 — see the docstring: must not raise
            self._deploy_error = f"{type(e).__name__}: {e}"
