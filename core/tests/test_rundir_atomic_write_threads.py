"""rundir._atomic_write must be safe when several threads of one process write the same file at once
(the temp file name is unique per call, not only per process)."""

from __future__ import annotations

import threading

from cap_evolve.rundir import _atomic_write


def test_atomic_write_same_path_from_many_threads(tmp_path):
    path = tmp_path / "conductor.json"
    n_threads, n_writes = 8, 100
    payloads = {t: (f"thread-{t}:" + "x" * 4000) for t in range(n_threads)}
    errors: list[BaseException] = []
    start = threading.Barrier(n_threads)

    def worker(t):
        try:
            start.wait()
            for _ in range(n_writes):
                _atomic_write(path, payloads[t])
        except BaseException as e:  # noqa: BLE001 - the test reports any failure
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    assert not errors, errors
    assert path.read_text(encoding="utf-8") in payloads.values(), "final file is not one whole write"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["conductor.json"], "temp files left behind"
