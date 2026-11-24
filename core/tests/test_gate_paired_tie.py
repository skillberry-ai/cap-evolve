from cap_evolve.gate import decide


def test_one_task_gain_rejected_at_every_n():
    for n in range(2, 201):
        d = decide(0.5, 0.5, mode="paired", paired_deltas=[1.0] + [0.0] * (n - 1), k_se=1.0)
        assert d.accept is False, n


def test_clearly_above_bar_still_accepts():
    d = decide(0.5, 0.6, mode="paired", paired_deltas=[0.1, 0.12, 0.09, 0.11] * 5, k_se=1.0)
    assert d.accept is True
