"""Provision the Skillberry Store + Proxy-Agent for the AppWorld blackbox approach, at the pinned commits.

    python provision_stack.py

The clones live where every blackbox benchmark keeps them: the repo's shared ``vendor/`` (or
``SPA_VENDOR_DIR`` when set), via ``blackbox_env.provision()``. That leaves an existing clone alone,
and this script never deletes one. A clone whose HEAD is not the pinned commit (``STORE_REF`` /
``AGENT_REF`` in blackbox_env.py) is an error: the AppWorld approach needs the proxy's context hooks,
so running on another commit would be silently wrong. To pick up a new pin, delete that clone
(e.g. ``rm -rf vendor/skillberry-agent``) and run this again.
"""

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "adapters"))
import appworld_tailoring  # noqa: E402

bb = appworld_tailoring.blackbox_env()


def head(d: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=d, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


def main() -> int:
    paths = bb.provision()
    bad = []
    for name, d, ref in (("store", bb.store_dir(), bb.STORE_REF), ("agent", bb.agent_dir(), bb.AGENT_REF)):
        got = head(Path(d))
        print(f"  {name}: {d} @ {got[:12] or '?'} ({'pinned' if got == ref else 'NOT the pinned ' + ref[:12]})")
        if got != ref:
            bad.append(str(d))
    if bad:
        print(f"  stale clone(s): delete {' '.join(bad)} and run this again to clone the pinned commit",
              file=sys.stderr)
        return 1
    print(f"  provisioned: {paths}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
