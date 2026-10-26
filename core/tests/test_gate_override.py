"""gate_override (K02R experiment switch): naive = accept iff mean paired delta >= 0, none = accept every decisive scored candidate;
absent key = stock gate untouched. Uses the real gate.decide and a real spec file."""
import pytest
from cap_evolve import gate as gate_mod, gate_override


def _decide(deltas, k_se=0.2, **kw):
    return gate_mod.decide(0.5, 0.5 + sum(deltas) / len(deltas), split="val", mode="paired", k_se=k_se, paired_deltas=deltas, coverage=1.0, **kw)


class RD:
    def __init__(self, tmp_path, spec):
        from cap_evolve import specfile
        self.root = tmp_path; (tmp_path / "spec.yaml").write_text(spec)
        self.events_path = tmp_path / "events.jsonl"
        import json
        self.events_path.write_text(json.dumps({"kind": "spec_resolved", "spec": str(tmp_path / "spec.yaml")}) + "\n")


def test_stock_path_has_no_override(tmp_path):
    assert gate_override.mode(RD(tmp_path, "gate_k_se: 0.2\n")) is None


def test_bad_value_raises(tmp_path):
    with pytest.raises(ValueError):
        gate_override.mode(RD(tmp_path, "gate_override: sometimes\n"))


def test_naive_accepts_zero_and_small_positive_that_stock_rejects():
    d = [0.0, 0.0, 0.0, 0.0]                      # mean 0: stock rejects (not > 0), naive accepts (>= 0)
    dec = _decide(d); assert not dec.accept
    sh = gate_override.apply(dec, "naive", 4); assert dec.accept and "GATE-NAIVE" in dec.reason and sh["accept"] is False
    d = [0.04, -0.04, 0.05, -0.04, 0.0, 0.0]      # tiny positive mean inside noise: stock (k=0.2) vs naive
    dec = _decide(d); stock = dec.accept
    gate_override.apply(dec, "naive", 6); assert dec.accept is True and isinstance(stock, bool)


def test_naive_rejects_negative_mean():
    d = [-0.05, -0.1, 0.0, 0.02]
    dec = _decide(d); gate_override.apply(dec, "naive", 4); assert not dec.accept and "<" in dec.reason


def test_none_accepts_a_clearly_worse_candidate_and_records_the_stock_verdict():
    dec = _decide([-0.3, -0.2, -0.4]); assert not dec.accept
    sh = gate_override.apply(dec, "none", 3); assert dec.accept and "GATE-NONE" in dec.reason and sh["accept"] is False


@pytest.mark.parametrize("m", ["naive", "none"])
def test_indecisive_and_unscored_are_never_accepted(m):
    dec = gate_mod.GateDecision(accept=False, reason="coverage", delta=0.0, indecisive=True)
    gate_override.apply(dec, m, 5); assert not dec.accept
    dec = _decide([0.1, 0.1]); dec.accept = False
    gate_override.apply(dec, m, 0); assert not dec.accept
