import json, os

# Figure out how materialize() sees the candidate: which files are components?
# From events.jsonl / run config: the capability is a skill-package at candidates/seed/
# Let's check git for the candidate dir contents.
import subprocess
out = subprocess.run(["git", "show", "--name-only", "--pretty=", "HEAD"], capture_output=True, text=True).stdout
print("Files in seed commit:")
print(out)
