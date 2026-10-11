# source this: container runtime + python envs for LOCAL benchmark runs (no secrets here).
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/podman/podman.sock     # podman's docker-compatible API (docker SDK + CLI shim)
export PYTHONDONTWRITEBYTECODE=1                                   # never write .pyc into the repo checkout
export BENCH=/home/dev/projects2/campaign-scratch/bench
export REPO=/home/dev/projects2/cap-evolve-campaign
# provider config is passed by the caller, NAMES ONLY (see benchmarks.md):
#   IBM_ETE_INT_API_BASE IBM_ETE_INT_API_KEY | IBM_ETE_API_BASE IBM_ETE_API_KEY | IBM_RITS_API_BASE IBM_RITS_API_KEY
