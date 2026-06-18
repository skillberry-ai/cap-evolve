# cap-evolve dashboard — backend

FastAPI service over cap-evolve run dirs. Read-only; reuses `cap_evolve.dashboard.reduce_run`.

## Dev
    pip install -e ../../core        # cap-evolve-core
    pip install -e .[dev]
    python -m pytest -q

## Run
    cap-evolve-dashboard --base .capevolve --port 7878
    # serves the built frontend (dashboard/frontend/dist) when present
