"""Load provider credentials into a dict without ever printing values.

Usage (library): from provider_env import load_all; cfg = load_all()
Only hostnames and key *names* are ever shown by redact().
"""
import json
import os
from urllib.parse import urlparse

RITS_FILE = "/home/dev/projects2/rits-env"
AZURE_FILE = "/home/dev/projects2/azure-openai-env"
CLAUDE_SETTINGS = os.path.expanduser("~/.claude/settings.json")


def _parse_env(path):
    out = {}
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.replace("export ", "").strip()
            out[k] = v.strip().strip('"').strip("'")
    return out


def load_all():
    cfg = {}
    if os.path.exists(RITS_FILE):
        e = _parse_env(RITS_FILE)
        # NB: the supplied file spells the key RITS_API_KET (sic).
        cfg["rits"] = {"base": e.get("RITS_URL"),
                       "key": e.get("RITS_API_KEY") or e.get("RITS_API_KET")}
    if os.path.exists(AZURE_FILE):
        e = _parse_env(AZURE_FILE)
        cfg["azure"] = {"base": e.get("AZURE_API_BASE"),
                        "key": e.get("AZURE_OPENAI_API_KEY"),
                        "version": e.get("AZURE_API_VERSION")}
    if os.path.exists(CLAUDE_SETTINGS):
        env = json.load(open(CLAUDE_SETTINGS)).get("env", {})
        cfg["litellm"] = {"base": env.get("ANTHROPIC_BASE_URL"),
                          "key": env.get("ANTHROPIC_AUTH_TOKEN")}
    return cfg


def redact(cfg):
    out = {}
    for p, c in cfg.items():
        out[p] = {k: (urlparse(v).netloc + urlparse(v).path if k == "base" and v else
                      ("<set>" if v else "<missing>") if k == "key" else v)
                  for k, v in c.items()}
    return out


if __name__ == "__main__":
    print(json.dumps(redact(load_all()), indent=1))
