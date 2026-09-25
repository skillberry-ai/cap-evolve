"""Deleting a skill requires deleting whatever depends on it first.

The store is an external service — skillberry-store at the tag ``blackbox_env.STORE_REF`` pins (0.2.1),
not this repo. There, ``skills_service.delete`` refuses outright while anything depends on the
skill::

    dependents = self.handler.dependency_manager.get_dependents(uuid)
    if dependents:
        raise ObjectInUseError("skill", uuid, dependents)      # -> HTTP 409

vMCP and vNFS servers register exactly that dependency when created against a skill, and they live
in the store rather than in the run — so an interrupted run leaves them behind in a store that keeps
running. The next run then failed EVERY rollout with "could not remove existing skill my_skill from
the store" (observed 2026-09-14: 50 tasks x 10 trials, coverage 0/50, and a baseline of 0.0 still
reported as a "floor").

These tests drive the real delete_skill against a fake store that enforces the store's own 409 rule,
because the bug was never in the HTTP calls themselves but in their ORDER, and in what a bare False
hides from the caller.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

BLACKBOX_ENV = (Path(__file__).resolve().parents[2]
           / "skills/interventions/llm-proxies/blackbox/scripts/blackbox_env.py")

SKILL_UUID = "skill-uuid-1111"


@pytest.fixture(scope="module")
def blackbox_env():
    spec = importlib.util.spec_from_file_location("blackbox_env_under_test", BLACKBOX_ENV)
    assert spec and spec.loader, f"could not load {BLACKBOX_ENV}"   # also satisfies the type checker
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeStore:
    """The subset of the store's HTTP surface delete_skill touches, with the 409 rule enforced.

    Models the store's actual precondition rather than trusting a mock to be called: DELETE
    /skills/<x> returns 409 for as long as any row still references it via ``skill_uuid``.
    """

    def __init__(self, *, skill=True, vmcp=(), vnfs=(), tools=(), snippets=()):
        self.skill = {"uuid": SKILL_UUID, "name": "my_skill",
                      "tool_uuids": list(tools),
                      "snippet_uuids": list(snippets)} if skill else None
        self.snippets = {sn: {"uuid": sn} for sn in snippets}
        self.vmcp = [dict(r) for r in vmcp]
        self.vnfs = [dict(r) for r in vnfs]
        self.tools = {t: {"uuid": t, "name": "tool-" + t, "tags": []} for t in tools}
        self.calls = []

    def _blocking(self):
        return ([("vmcp", r) for r in self.vmcp if r.get("skill_uuid") == SKILL_UUID]
                + [("vnfs", r) for r in self.vnfs if r.get("skill_uuid") == SKILL_UUID])

    def curl(self, args, timeout=60):
        verb = args[args.index("-X") + 1]
        url = args[-1]
        path = "/" + url.split("/", 3)[3] if url.startswith("http") else url
        self.calls.append(verb + " " + path.split("?")[0])

        if verb == "GET" and path.startswith("/skills/"):
            return (200, json.dumps(self.skill)) if self.skill else (404, "not found")
        if verb == "GET" and path.startswith("/vmcp_servers/"):
            return 200, json.dumps(self.vmcp)
        if verb == "GET" and path.startswith("/vnfs_servers/"):
            return 200, json.dumps(self.vnfs)
        if verb == "GET" and path.startswith("/tools/"):
            uuid = path.split("/tools/")[1].split("?")[0]
            if not uuid:                                  # the LIST endpoint, used by purge_orphans
                return 200, json.dumps(list(self.tools.values()))
            return (200, json.dumps(self.tools[uuid])) if uuid in self.tools else (404, "gone")
        if verb == "GET" and path.startswith("/snippets/"):
            uuid = path.split("/snippets/")[1].split("?")[0]
            if not uuid:
                return 200, json.dumps(list(self.snippets.values()))
            return (200, json.dumps(self.snippets[uuid])) if uuid in self.snippets else (404, "gone")
        if verb == "DELETE" and path.startswith("/vmcp_servers/"):
            uuid = path.rsplit("/", 1)[-1]
            self.vmcp = [r for r in self.vmcp if r.get("uuid") != uuid]
            return 204, ""
        if verb == "DELETE" and path.startswith("/vnfs_servers/"):
            uuid = path.rsplit("/", 1)[-1]
            self.vnfs = [r for r in self.vnfs if r.get("uuid") != uuid]
            return 204, ""
        if verb == "DELETE" and path.startswith("/skills/"):
            blocking = self._blocking()
            if blocking:
                named = ", ".join(k + ":" + r["uuid"] for k, r in blocking)
                return 409, json.dumps(
                    {"detail": "skill " + SKILL_UUID + " in use by [" + named + "]"})
            self.skill = None
            return 204, ""
        if verb == "DELETE" and path.startswith("/tools/"):
            self.tools.pop(path.rsplit("/", 1)[-1], None)
            return 204, ""
        if verb == "DELETE" and path.startswith("/snippets/"):
            uuid = path.rsplit("/", 1)[-1]
            if uuid not in self.snippets:
                return 404, "gone"
            del self.snippets[uuid]
            return 204, ""
        # Anything unmodelled must NOT look like success: _delete_object treats 404 as "already
        # gone", so returning 404 here would let an unexercised path pass vacuously.
        return 501, f"FakeStore does not model {verb} {path}"

    def install(self, blackbox_env, monkeypatch):
        monkeypatch.setattr(blackbox_env, "_curl", self.curl)
        monkeypatch.setattr(blackbox_env, "store_port", lambda: "8000")
        monkeypatch.setattr(blackbox_env, "load_env", lambda: None)
        return self


# ---------------------------------------------------------------------------
# The three entry paths run.sh and the optimisation loop actually take
# ---------------------------------------------------------------------------

def test_1_clean_store_with_a_properly_imported_skill(blackbox_env, monkeypatch):
    """Nothing depends on the skill: the delete succeeds and no dependent is deleted."""
    store = FakeStore().install(blackbox_env, monkeypatch)

    assert blackbox_env.delete_skill("my_skill") is True
    assert store.skill is None
    assert not [c for c in store.calls
                if c.startswith("DELETE /vmcp") or c.startswith("DELETE /vnfs")]


def test_2_store_left_holding_a_previous_skill_with_a_live_vmcp(blackbox_env, monkeypatch):
    """The interrupted-run case: a vMCP server survives in the store and blocked every rollout."""
    store = FakeStore(vmcp=[{"uuid": "vmcp-1", "skill_uuid": SKILL_UUID}]).install(
        blackbox_env, monkeypatch)

    assert blackbox_env.delete_skill("my_skill") is True
    assert store.skill is None, "the skill must actually be gone"
    assert store.vmcp == [], "the blocking dependent must be gone too"
    assert store.calls.index("DELETE /vmcp_servers/vmcp-1") < \
        store.calls.index("DELETE /skills/my_skill"), "the order IS the fix"


def test_3_candidate_switch_clears_dependents_of_both_kinds(blackbox_env, monkeypatch):
    """Mid-run reimport, with both dependent kinds present at once."""
    store = FakeStore(vmcp=[{"uuid": "vmcp-1", "skill_uuid": SKILL_UUID},
                            {"uuid": "vmcp-2", "skill_uuid": SKILL_UUID}],
                      vnfs=[{"uuid": "vnfs-1", "skill_uuid": SKILL_UUID}]).install(
        blackbox_env, monkeypatch)

    assert blackbox_env.delete_skill("my_skill") is True
    assert (store.vmcp, store.vnfs, store.skill) == ([], [], None)


# ---------------------------------------------------------------------------
# Not over-reaching, and not hiding failures
# ---------------------------------------------------------------------------

def test_a_dependent_of_another_skill_is_left_alone(blackbox_env, monkeypatch):
    """It cannot be what blocks this skill, and deleting it would break the other one."""
    other = {"uuid": "vmcp-other", "skill_uuid": "skill-uuid-9999"}
    store = FakeStore(vmcp=[{"uuid": "vmcp-1", "skill_uuid": SKILL_UUID}, dict(other)]).install(
        blackbox_env, monkeypatch)

    assert blackbox_env.delete_skill("my_skill") is True
    assert store.vmcp == [other], "only the blocking dependent may be removed"


def test_a_missing_skill_is_success_and_touches_nothing(blackbox_env, monkeypatch):
    """Callers always delete-then-import, so 404 is the clean-slate path."""
    store = FakeStore(skill=False, vmcp=[{"uuid": "vmcp-1", "skill_uuid": SKILL_UUID}]).install(
        blackbox_env, monkeypatch)

    assert blackbox_env.delete_skill("my_skill") is True
    assert store.vmcp == [{"uuid": "vmcp-1", "skill_uuid": SKILL_UUID}]


def test_a_surviving_409_names_the_dependent_instead_of_returning_false(blackbox_env, monkeypatch):
    """An unknown dependent kind must be diagnosable in one read.

    "could not remove existing skill my_skill from the store" — no status code, no named dependent —
    is what made this take two days. If a third kind appears, the store names it in the 409 body and
    that must reach the operator.
    """
    FakeStore(vmcp=[{"uuid": "vmcp-ghost", "skill_uuid": SKILL_UUID}]).install(blackbox_env, monkeypatch)
    monkeypatch.setattr(blackbox_env, "delete_skill_dependents", lambda _uuid: [])   # unknown kind

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")

    msg = str(err.value)
    assert "409" in msg and "vmcp-ghost" in msg
    assert "_SKILL_DEPENDENT_KINDS" in msg, "the message must say how to fix it"


def test_an_unexpected_status_is_raised_with_its_body(blackbox_env, monkeypatch):
    store = FakeStore().install(blackbox_env, monkeypatch)
    real = store.curl

    def broken(args, timeout=60):
        if args[args.index("-X") + 1] == "DELETE" and "/skills/" in args[-1]:
            return 500, "Error deleting skill: disk on fire"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", broken)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    assert "500" in str(err.value) and "disk on fire" in str(err.value)


def test_dependents_are_matched_on_skill_uuid_not_name(blackbox_env, monkeypatch):
    """add_dependent registers the skill's UUID, so a row without skill_uuid is not a dependent."""
    store = FakeStore(vmcp=[{"uuid": "vmcp-nolink"}]).install(blackbox_env, monkeypatch)

    assert blackbox_env.delete_skill_dependents(SKILL_UUID) == []
    assert store.vmcp == [{"uuid": "vmcp-nolink"}]


def test_a_failed_dependent_delete_is_reported(blackbox_env, monkeypatch):
    store = FakeStore(vmcp=[{"uuid": "vmcp-1", "skill_uuid": SKILL_UUID}]).install(
        blackbox_env, monkeypatch)
    real = store.curl

    def stubborn(args, timeout=60):
        if args[args.index("-X") + 1] == "DELETE" and "/vmcp_servers/" in args[-1]:
            return 500, "nope"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", stubborn)

    assert blackbox_env.delete_skill_dependents(SKILL_UUID) == ["vmcp_server/vmcp-1"], \
        "name what could not be deleted; a bool cannot be reported to the operator"

# ---------------------------------------------------------------------------
# One failure mode: delete_skill returns True or raises with the reason
#
# It used to return a bare False from four different places, which reset_store_to_skill could only
# report as "could not remove existing skill <name>" — no status, no named object. Every failure the
# store reports comes with a reason; none of them should be thrown away.
# ---------------------------------------------------------------------------

def test_an_unreadable_manifest_raises_with_the_status(blackbox_env, monkeypatch):
    store = FakeStore().install(blackbox_env, monkeypatch)
    real = store.curl

    def down(args, timeout=60):
        if args[args.index("-X") + 1] == "GET" and "/skills/" in args[-1]:
            return 503, "upstream unavailable"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", down)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    assert "503" in str(err.value) and "upstream unavailable" in str(err.value)


def test_curl_itself_failing_says_the_store_may_be_down(blackbox_env, monkeypatch):
    """_curl returns -1 when curl cannot run at all — the commonest cause is no store."""
    FakeStore().install(blackbox_env, monkeypatch)
    monkeypatch.setattr(blackbox_env, "_curl", lambda args, timeout=60: (-1, ""))

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    assert "is the store up" in str(err.value)


def test_unparseable_json_raises_rather_than_returning_false(blackbox_env, monkeypatch):
    FakeStore().install(blackbox_env, monkeypatch)
    monkeypatch.setattr(blackbox_env, "_curl", lambda args, timeout=60: (200, "<html>nope</html>"))

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    assert "unparseable" in str(err.value) and "nope" in str(err.value)


def test_a_tool_that_will_not_delete_is_named_not_hidden(blackbox_env, monkeypatch):
    """The skill IS gone at that point, so "could not remove the skill" would be a lie — and the
    orphan matters: the next import mints fresh UUIDs under the same names."""
    store = FakeStore(tools=["tool-stuck"]).install(blackbox_env, monkeypatch)
    real = store.curl

    def stubborn(args, timeout=60):
        if args[args.index("-X") + 1] == "DELETE" and "/tools/" in args[-1]:
            return 500, "in use"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", stubborn)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")

    msg = str(err.value)
    assert "tool/tool-stuck" in msg, "name the object that could not be deleted"
    assert "was deleted" in msg, "be clear the SKILL went away; it is the tool that did not"
    assert store.skill is None


def test_delete_skill_never_returns_false(blackbox_env, monkeypatch):
    """The contract in one assertion: True, or an exception carrying the reason."""
    FakeStore().install(blackbox_env, monkeypatch)
    assert blackbox_env.delete_skill("my_skill") is True


# ---------------------------------------------------------------------------
# Review follow-ups (PR #489) and one gap found auditing the store at 0.2.1
# ---------------------------------------------------------------------------

def test_a_dependent_that_will_not_delete_is_reported_even_if_the_skill_deletes(
        blackbox_env, monkeypatch):
    """The corner the first round of tests missed.

    deps_stuck used to be read only inside the 409 branch, so a dependent that failed to delete
    while the skill delete still succeeded left an orphan behind and delete_skill returned True.
    Probably unreachable — a surviving BLOCKING dependent should make the skill delete 409 — but it
    read as an oversight, and a stuck tool already raised while a stuck vMCP row did not.
    """
    store = FakeStore(vmcp=[{"uuid": "vmcp-1", "skill_uuid": SKILL_UUID}]).install(
        blackbox_env, monkeypatch)
    real = store.curl

    def dependent_wont_die(args, timeout=60):
        verb = args[args.index("-X") + 1]
        if verb == "DELETE" and "/vmcp_servers/" in args[-1]:
            return 500, "transient"          # fails, but the row stays -> skill delete would 409
        if verb == "DELETE" and "/skills/" in args[-1]:
            store.skill = None               # force the "skill deleted anyway" corner
            return 204, ""
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", dependent_wont_die)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    assert "vmcp_server/vmcp-1" in str(err.value), "the orphaned dependent must be named"


def test_a_manifest_without_a_uuid_raises_instead_of_matching_on_the_name(blackbox_env, monkeypatch):
    """`manifest.get("uuid") or skill_name` was a fallback no real store could exercise.

    A dependent's skill_uuid always holds a UUID, so matching it against a NAME can never hit
    anything: the cleanup would silently do nothing and the failure would resurface as a 409 one
    step removed from its cause.
    """
    store = FakeStore().install(blackbox_env, monkeypatch)
    store.skill = {"name": "my_skill", "tool_uuids": [], "snippet_uuids": []}   # no uuid

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    assert "has no uuid" in str(err.value)


def test_tools_that_depend_on_each_other_are_deleted_in_a_workable_order(blackbox_env, monkeypatch):
    """A tool auto-registers a dependency on every tool it calls by bare name
    (tools_service.py:326 at 0.2.1), and tools_service.delete refuses while a tool has dependents
    (tools_service.py:672). Deleting a skill's tools in manifest order therefore fails whenever one
    wrapper calls another and the callee comes first — so retry until a pass frees nothing.
    """
    store = FakeStore(tools=["callee", "caller"]).install(blackbox_env, monkeypatch)
    real = store.curl

    def with_tool_deps(args, timeout=60):
        # "callee" cannot go while "caller" still exists, exactly as the store would refuse it.
        if (args[args.index("-X") + 1] == "DELETE" and args[-1].endswith("/tools/callee")
                and "caller" in store.tools):
            return 409, "tool callee in use by [tool:caller]"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", with_tool_deps)

    assert blackbox_env.delete_skill("my_skill") is True, "the retry pass must free the callee"
    assert store.tools == {}, "both tools must be gone"


def test_a_genuine_cycle_stops_instead_of_looping(blackbox_env, monkeypatch):
    """The no-progress exit. Two tools that each block the other must be reported, not spun on."""
    store = FakeStore(tools=["a", "b"]).install(blackbox_env, monkeypatch)
    real = store.curl

    def deadlocked(args, timeout=60):
        if args[args.index("-X") + 1] == "DELETE" and "/tools/" in args[-1]:
            return 409, "in use"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", deadlocked)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    msg = str(err.value)
    assert "tool/a" in msg and "tool/b" in msg, "name every object that stayed stuck"


# ---------------------------------------------------------------------------
# The rest of that retry block: snippets, and more than one dependency layer
# ---------------------------------------------------------------------------

def test_snippets_go_with_the_skill_and_are_not_filtered_by_protection(blackbox_env, monkeypatch):
    """Tools are filtered through Protection; snippets are deliberately not.

    A snippet belongs to its skill, so there is no frozen-substrate equivalent to protect. Until now
    no test touched snippets at all, and FakeStore did not model DELETE /snippets/ — which meant the
    unexercised path would have "passed" on the 404-is-already-gone rule.
    """
    store = FakeStore(tools=["t1"], snippets=["s1", "s2"]).install(blackbox_env, monkeypatch)

    assert blackbox_env.delete_skill("my_skill") is True
    assert store.snippets == {}, "the skill's snippets must be deleted with it"
    assert store.tools == {}


def test_a_snippet_that_will_not_delete_is_named(blackbox_env, monkeypatch):
    """The comment claims a shared snippet is "refused by the store anyway and reported below" —
    this is the test for the reported-below half."""
    store = FakeStore(snippets=["s-shared"]).install(blackbox_env, monkeypatch)
    real = store.curl

    def shared(args, timeout=60):
        if args[args.index("-X") + 1] == "DELETE" and "/snippets/" in args[-1]:
            return 409, "snippet s-shared in use by [skill:other]"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", shared)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.delete_skill("my_skill")
    assert "snippet/s-shared" in str(err.value)
    assert store.skill is None, "the skill still went away; it is the snippet that did not"


def test_a_three_deep_chain_needs_more_than_one_retry_pass(blackbox_env, monkeypatch):
    """"One layer at a time" — a single retry is not enough, so prove the loop keeps going.

    a is blocked by b, and b is blocked by c: c goes first, then b, then a. Manifest order is the
    worst case (a, b, c), so a naive single retry would leave a behind.
    """
    store = FakeStore(tools=["a", "b", "c"]).install(blackbox_env, monkeypatch)
    real = store.curl
    blocked_by = {"a": "b", "b": "c"}
    passes = {"n": 0}

    def layered(args, timeout=60):
        verb = args[args.index("-X") + 1]
        url = args[-1]
        if verb == "DELETE" and "/tools/" in url:
            uuid = url.rsplit("/", 1)[-1]
            blocker = blocked_by.get(uuid)
            if blocker and blocker in store.tools:
                passes["n"] += 1
                return 409, f"tool {uuid} in use by [tool:{blocker}]"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", layered)

    assert blackbox_env.delete_skill("my_skill") is True
    assert store.tools == {}, "every tool in the chain must be freed"
    assert passes["n"] >= 3, "a single pass cannot resolve a two-layer chain"


# ---------------------------------------------------------------------------
# purge_orphans runs one line after delete_skill in reset_store_to_skill, on the same class of
# objects. It had the single-pass bug delete_skill was just fixed for, so an ordering fix in one and
# not the other would only move the failure.
# ---------------------------------------------------------------------------

def test_purge_orphans_retries_when_orphans_depend_on_each_other(blackbox_env, monkeypatch):
    """Same chain as the skill's own tools: b blocks a, so listing order alone is not enough."""
    store = FakeStore(skill=False, tools=["a", "b"]).install(blackbox_env, monkeypatch)
    real = store.curl

    def layered(args, timeout=60):
        url = args[-1]
        if (args[args.index("-X") + 1] == "DELETE" and url.endswith("/tools/a")
                and "b" in store.tools):
            return 409, "tool a in use by [tool:b]"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", layered)

    assert blackbox_env.purge_orphans() is True
    assert store.tools == {}, "the retry pass must free the blocked orphan"


def test_purge_orphans_names_what_it_could_not_delete(blackbox_env, monkeypatch):
    """It used to return a bare False, which reset_store_to_skill reported as "could not purge
    leftover unprotected tools/snippets" — no names, the same unactionable message this PR is about.
    """
    store = FakeStore(skill=False, tools=["wedged"]).install(blackbox_env, monkeypatch)
    real = store.curl

    def wedged(args, timeout=60):
        if args[args.index("-X") + 1] == "DELETE" and "/tools/" in args[-1]:
            return 409, "in use"
        return real(args, timeout)

    monkeypatch.setattr(blackbox_env, "_curl", wedged)

    with pytest.raises(RuntimeError) as err:
        blackbox_env.purge_orphans()
    assert "tool/wedged" in str(err.value)


def test_purge_orphans_still_keeps_the_protected_substrate(blackbox_env, monkeypatch):
    """The frozen primitives must survive every redeploy — unchanged behaviour, now pinned."""
    store = FakeStore(skill=False, tools=["wrapper", "primitive"]).install(blackbox_env, monkeypatch)
    store.tools["primitive"]["tags"] = ["frozen"]

    assert blackbox_env.purge_orphans(blackbox_env.Protection(tags=("frozen",))) is True
    assert list(store.tools) == ["primitive"], "protected tools are kept, orphans go"


def test_purge_orphans_clears_snippets_too(blackbox_env, monkeypatch):
    store = FakeStore(skill=False, tools=["t"], snippets=["s"]).install(blackbox_env, monkeypatch)

    assert blackbox_env.purge_orphans() is True
    assert (store.tools, store.snippets) == ({}, {})
