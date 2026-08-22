# Running Docker/Podman-based benchmarks on CCC (no admin)

**Audience:** IBM CCC users who want to run tools that assume `docker` +
`docker compose` v2, on a locked-down cluster where you have no root, no
`sudo`, no `/etc/subuid` entry, and (on compute nodes) no systemd user
session. This document is a walkthrough of the exact set of userspace
workarounds we found through trial and error while getting BenchFlow +
SkillsBench + Claude Code running for the `cap-evolve` project. Every step
is reproducible without admin help.

**Written:** 2026-07-29. **Updated:** 2026-07-30 with these iterative
fixes (each caught a specific class of failing task):
- v2 → v3: `chown`/`chgrp` wrappers (postinst chown failures)
- v3 → v4: `useradd`/`groupadd`/`usermod`/`groupmod`/`adduser`/`addgroup`
  wrappers (packages that create system users)
- v4 → v5: `dpkg-statoverride` wrapper (dbus's setuid-helper ownership
  fix, and everything downstream — libpam-systemd, gnumeric, libgtk,
  libgoffice, libreoffice)
- PATH-ordering fix so our `docker` shim isn't shadowed by
  `/usr/bin/docker`
- `poppler-utils` + `build-essential` preinstalled in the base image

Environment: CCC RHEL 9.6, Podman 5.2.2 with podman-docker shim at
`/usr/bin/docker`, benchflow 0.6.5 installed via `uv tool`.

---

## Why this is hard

CCC's rootless podman is missing three things a typical Docker/podman
setup gives you for free:

1. **A subuid range in `/etc/subuid`/`/etc/subgid`.** Standard rootless
   setups have `yourname:100000:65536` — 65 536 UIDs to map into
   containers. On CCC your user isn't listed, so the rootless namespace
   only has UID 0 → your host UID. Every `useradd`/`chown`/setuid inside
   a container to a different UID fails with `EINVAL`.

2. **A systemd user session on compute nodes.** Login nodes have one,
   compute nodes don't. Aardvark-dns (podman's DNS resolver for bridge
   networks) needs systemd to spin up a transient scope; without it,
   `podman-compose up` fails at container start.

3. **A quiet `docker` command.** `/usr/bin/docker` on CCC is
   `podman-docker`, which prints `Emulate Docker CLI using podman.
   Create /etc/containers/nodocker to quiet msg.` to **stdout** on every
   invocation. Tools that capture the stdout of `docker` commands end
   up embedding that string in their results and downstream commands.

All three have known workarounds. All three are userspace-only.

---

## What you get

After running the setup below, on any CCC node (login or compute) you can:

```bash
source <path-to-cap-evolve>/scripts/ccc/setup_podman.sh   # one line
docker run --rm ubuntu:24.04 uname -a                              # works
docker compose -f your.yaml up -d                                  # works
bench eval run --sandbox docker ...                                # works
```

with no admin help. The setup script is idempotent — sourcing it again in
another shell is a no-op.

---

## Prerequisites

- CCC account with home in `/u/<user>` and access to `/dccstor/...` for
  shared data. Read/execute permission on
  `<path-to-cap-evolve>/scripts/ccc/setup_podman.sh` (or copy it
  to your own path).
- Podman 5.2+ and podman-docker on the host (default on current CCC).
- `dbus-daemon` in your `$PATH`. Anaconda's works
  (`~/anaconda3/bin/dbus-daemon`) if you don't have it elsewhere.
- Python 3.10+ for anything you run on top.

---

## One-time setup (do this once, persists in `$HOME`)

### 1) Install Docker Compose v2 as a user CLI plugin

Podman's default compose provider is `/usr/bin/podman-compose` (Python
1.5.0), which has a **different CLI** from Docker Compose v2 — it
doesn't accept `--project-directory` and other v2 flags that BenchFlow
(and most modern tooling) use. Install the real Compose v2 binary:

```bash
mkdir -p ~/.docker/cli-plugins
curl -fsSL -o ~/.docker/cli-plugins/docker-compose \
  "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64"
chmod +x ~/.docker/cli-plugins/docker-compose
~/.docker/cli-plugins/docker-compose version   # should print "Docker Compose version vX.Y.Z"
```

### 2) Point podman at Compose v2 (and disable systemd/dbus paths)

Write `~/.config/containers/containers.conf`:

```bash
mkdir -p ~/.config/containers
cat > ~/.config/containers/containers.conf <<'EOF'
[containers]
# Compute nodes have no systemd user session, so avoid systemd/dbus paths.
cgroups = "disabled"

[engine]
compose_providers = ["/u/<YOUR_USER>/.docker/cli-plugins/docker-compose"]
compose_warning_logs = false
# Same reason: don't call dbus, don't use systemd cgroup manager.
cgroup_manager = "cgroupfs"
events_logger = "file"
EOF
```

Replace `<YOUR_USER>` with your username (the absolute path must resolve
on both login and compute nodes).

### 3) Nothing else is one-time — the rest is done by `setup_podman.sh` per session.

---

## Per-session setup (per compute node)

Source `setup_podman.sh` at the start of every session on a fresh node.
The script is idempotent, so sourcing it in an existing session is fine
too.

```bash
source <path-to-cap-evolve>/scripts/ccc/setup_podman.sh
```

You'll see:

```
[setup_podman] patched ubuntu:24.04 for apt-in-rootless (log: /tmp/podman-run-<UID>/patched-ubuntu-build.log)
[setup_podman] XDG_RUNTIME_DIR=/tmp/podman-run-<UID>
[setup_podman] graphroot=/tmp/podman-<UID>
[setup_podman] DOCKER_HOST=unix:///tmp/podman-run-<UID>/podman.sock
```

On the very first source on a fresh node, the "patched ubuntu:24.04"
step takes 2-3 minutes (see "What the script does" below). On subsequent
sources on the same node it's instant.

### What the script does

Read the file for the full detail — every action has a why. In brief:

1. **Writes `~/.config/containers/storage.conf`** with `graphroot` and
   `runroot` under `/tmp/podman-<UID>` and `/tmp/podman-run-<UID>` (host-
   local, since GPFS can't hold overlay). Sets
   `[storage.options.overlay] ignore_chown_errors = "true"` — this lets
   the image unpack skip lchown calls that would need UID 42 (which we
   don't have in our namespace). Without this,
   `podman pull ubuntu:24.04` fails at `/etc/gshadow`.

2. **Exports `XDG_RUNTIME_DIR=/tmp/podman-run-<UID>`.** On compute nodes
   `/run/user/<UID>` doesn't exist (no systemd), and podman refuses to
   start without a runtime dir.

3. **Installs a userspace `docker` shim at `~/.local/bin/docker`** that
   just execs `podman "$@"` with no chatty prefix. See "Why this is
   hard" §3 above. Prepends `~/.local/bin` to `PATH` if missing.

4. **Starts a private `dbus-daemon`** at
   `$XDG_RUNTIME_DIR/dbus.sock`, exports
   `DBUS_SESSION_BUS_ADDRESS=unix:path=...`. Some podman/netavark paths
   assume a session bus is present even when we've configured them not
   to.

5. **Starts `podman system service`** at
   `$XDG_RUNTIME_DIR/podman.sock`, exports
   `DOCKER_HOST=unix://...`. This is the API socket Compose v2 talks to.
   The script is idempotent — before starting, it kills any leftover
   `podman system service` processes and their sockets. Without this
   check, multiple sourcings ended up with 5 zombie services fighting
   for the SQLite DB and producing "attempt to write a readonly
   database" errors.

6. **Builds a patched local `docker.io/library/ubuntu:24.04`** with
   four groups of fixes baked in:
   - `/etc/apt/apt.conf.d/00-rootless` sets
     `APT::Sandbox::User "root";` (so apt doesn't try to setuid to
     `_apt` = UID 42, which we can't map) and
     `APT::Install-Recommends "false";` (so we don't pull in
     `libc-devtools`/`libgd3`/`fontconfig-config` whose postinst scripts
     do their own chown to non-root UIDs and fail).
   - **Wraps a set of ownership/user-management binaries** to swallow
     "Invalid argument" failures. Current list:
     - `chown`, `chgrp` — postinst scripts do `chown fontconfig:root /...`
     - `useradd`, `groupadd`, `usermod`, `groupmod`, `adduser`,
       `addgroup` — packages that create system users (`_dbus`,
       `messagebus`, `systemd-network`, `fontconfig`, etc.)
     - `dpkg-statoverride` — dbus (and other packages) use it to set
       the setuid bit on their launch helpers. It calls `fchown()` via
       libc, so wrapping shell-level `chown` alone doesn't cover it.

     Each wrapper is a 2-line `sh` script that calls the real binary
     (preserved at `<name>.real`) and returns 0 regardless of its
     exit code. Files still get created, just without correct
     ownership — usually fine, since the container's rootless namespace
     doesn't enforce those UIDs anyway.
   - Pre-installs `python3 python3-pip curl poppler-utils build-essential`
     so downstream Dockerfiles that install these packages find them
     already present and get a fast no-op. `build-essential` is
     ~500 MB but pays for itself across tasks: multiple SkillsBench
     Dockerfiles pull it in transitively, and the tail of failing
     postinst scripts it drags in is the biggest source of image-build
     failures on CCC.

   Any downstream `FROM ubuntu:24.04` picks up our patched local image
   (podman uses local before remote when tags match).

7. **Prepends `~/.local/bin` to `$PATH`** — not just "adds if missing"
   but explicitly puts it FIRST. If a login script has already added
   `~/.local/bin` to a later position, our `docker` shim (§3) would be
   shadowed by `/usr/bin/docker`, and every rollout would inherit the
   "Emulate Docker CLI..." message → garbled `-w` arg → `rc=127` at
   agent exec. This bug ate a whole 30-minute baseline before we
   spotted the PATH ordering issue.

---

## For BenchFlow-based tooling (SkillsBench, etc.) specifically

Two more patches are needed to bench itself. These affect `bench`'s
site-packages (`~/.local/share/uv/tools/benchflow/lib/.../benchflow/`);
they survive across sessions but are lost on `uv tool install --force`.

### A) Force host networking in every task container

BenchFlow's compose base yaml sets up a bridge network by default.
Bridge → netavark → aardvark-dns → systemd → fail on compute nodes.
Force host networking so aardvark isn't invoked at all:

```bash
python3 - <<'PY'
import shutil
p = "/u/<YOUR_USER>/.local/share/uv/tools/benchflow/lib/python3.12/site-packages/benchflow/sandbox/_compose_files/docker-compose-base.yaml"
if not __import__("os").path.exists(p + ".orig"):
    shutil.copy(p, p + ".orig")
s = open(p).read()
old = 'services:\n  main:\n    labels:'
new = 'services:\n  main:\n    # CCC workaround: skip bridge network; aardvark-dns needs systemd\n    network_mode: host\n    labels:'
if old in s:
    open(p, "w").write(s.replace(old, new))
    print("patched: network_mode: host")
else:
    print("already patched or file changed")
PY
```

**Trade-off:** the container shares the host's network stack. That means
no port isolation and no per-container hostname. Fine for tasks that
don't listen on ports (which is 99% of SkillsBench).

### B) Bypass `docker compose cp` (which fails on our UID namespace)

`docker compose cp` preserves the source file's ownership when copying
between host and container. Since our host UIDs (561567:608693 in my
case) don't exist inside the container's rootless namespace, every
`cp` blows up on `lchown`. The fix: replace bench's cp-based upload and
download with `docker compose exec -T` piped through `tar`, so the
container-side tar (running as root) owns everything.

Apply the upload patch:

```bash
python3 - <<'PY'
import re
p = "/u/<YOUR_USER>/.local/share/uv/tools/benchflow/lib/python3.12/site-packages/benchflow/sandbox/docker.py"
s = open(p).read()

helper = '''    async def _upload_via_exec(self, source_path, target_path: str, is_dir: bool) -> None:
        """CCC workaround: docker compose cp preserves source UIDs which fail
        to lchown inside rootless-podman (no /etc/subuid entry). We bypass cp
        by streaming the file/dir into the container via `exec -T` + stdin —
        the exec process runs as root, so files land as root:root and no
        cross-namespace chown is attempted.
        """
        import io as _io
        import tarfile as _tar
        buf = _io.BytesIO()
        def _root_owned(ti):
            ti.uid = 0; ti.gid = 0
            ti.uname = "root"; ti.gname = "root"
            return ti
        if is_dir:
            with _tar.open(fileobj=buf, mode="w") as tf:
                tf.add(str(source_path), arcname=".", filter=_root_owned)
            remote_cmd = f"tar xf - --no-same-owner -C {shlex.quote(target_path)}"
        else:
            with open(source_path, "rb") as f:
                data = f.read()
            with _tar.open(fileobj=buf, mode="w") as tf:
                info = _tar.TarInfo(name="_upload")
                info.size = len(data)
                info.mode = 0o644
                info.uid = 0; info.gid = 0
                info.uname = "root"; info.gname = "root"
                tf.addfile(info, _io.BytesIO(data))
            remote_cmd = (
                f"tar xf - --no-same-owner -C /tmp && "
                f"mv /tmp/_upload {shlex.quote(target_path)}"
            )
        full_command = [
            "docker", "compose", "--project-name",
            _sanitize_docker_compose_project_name(self.session_id),
            "--project-directory",
            str(self.environment_dir.resolve().absolute()),
        ]
        for path in self._docker_compose_paths:
            full_command.extend(["-f", str(path.resolve().absolute())])
        full_command.extend(["exec", "-T", "main", "sh", "-c", remote_cmd])
        env = self._docker_compose_env()
        process = await asyncio.create_subprocess_exec(
            *full_command,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout_bytes, _ = await process.communicate(input=buf.getvalue())
        if process.returncode != 0:
            raise RuntimeError(
                f"upload_via_exec failed (rc={process.returncode}): "
                f"{stdout_bytes.decode(errors='replace')}"
            )

    async def upload_file'''

old_upload_file = '''    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        target_parent = str(Path(target_path).parent)
        if target_parent not in {"", "."}:
            await self.exec(f"mkdir -p {shlex.quote(target_parent)}", user="root")
        await self._run_docker_compose_command(
            ["cp", str(source_path), f"main:{target_path}"],
            check=True,
        )'''
new_upload_file = '''    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        target_parent = str(Path(target_path).parent)
        if target_parent not in {"", "."}:
            await self.exec(f"mkdir -p {shlex.quote(target_parent)}", user="root")
        await self._upload_via_exec(source_path, target_path, is_dir=False)'''

if "_upload_via_exec" not in s:
    assert old_upload_file in s
    s = s.replace(old_upload_file, helper.replace("    async def upload_file", "").rstrip() + "\n\n" + new_upload_file, 1)
    old_dir_call = '''        await self._run_docker_compose_command(
            ["cp", f"{source_dir}/.", f"{service}:{target_dir}"],
            check=True,
        )'''
    new_dir_call = '''        await self._upload_via_exec(source_dir, target_dir, is_dir=True)'''
    s = s.replace(old_dir_call, new_dir_call, 1)
    open(p, "w").write(s)
    print("upload patch applied")
else:
    print("upload patch already applied")
PY
```

Apply the download patch (mirrors the upload — pipe tar from container
stdout to host):

```bash
python3 - <<'PY'
p = "/u/<YOUR_USER>/.local/share/uv/tools/benchflow/lib/python3.12/site-packages/benchflow/sandbox/docker.py"
s = open(p).read()

helper = '''    async def _download_via_exec(self, source_path: str, target_path, is_dir: bool, service: str = "main") -> None:
        """CCC workaround: reverse of _upload_via_exec. Stream a tar of the
        container-side path to our stdout, unpack into the host target dir.
        """
        import io as _io
        import os as _os
        import tarfile as _tar
        if is_dir:
            remote_cmd = f"tar cf - -C {shlex.quote(source_path)} ."
            _os.makedirs(str(target_path), exist_ok=True)
        else:
            parent = str(Path(source_path).parent) or "/"
            name = Path(source_path).name
            remote_cmd = f"tar cf - -C {shlex.quote(parent)} {shlex.quote(name)}"
        full_command = [
            "docker", "compose", "--project-name",
            _sanitize_docker_compose_project_name(self.session_id),
            "--project-directory",
            str(self.environment_dir.resolve().absolute()),
        ]
        for path in self._docker_compose_paths:
            full_command.extend(["-f", str(path.resolve().absolute())])
        full_command.extend(["exec", "-T", service, "sh", "-c", remote_cmd])
        env = self._docker_compose_env()
        process = await asyncio.create_subprocess_exec(
            *full_command,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f"download_via_exec failed (rc={process.returncode}): "
                f"{stderr_bytes.decode(errors='replace')}"
            )
        buf = _io.BytesIO(stdout_bytes)
        with _tar.open(fileobj=buf, mode="r|") as tf:
            if is_dir:
                tf.extractall(str(target_path), filter="data")
            else:
                import tempfile as _tempfile, shutil as _shutil
                with _tempfile.TemporaryDirectory() as td:
                    tf.extractall(td, filter="data")
                    src_extracted = _os.path.join(td, Path(source_path).name)
                    _shutil.move(src_extracted, str(target_path))

    async def download_file'''

old_download_file = '''    async def download_file(self, source_path: str, target_path: Path | str) -> None:
        await self._chown_to_host_user(source_path)
        await self._run_docker_compose_command(
            ["cp", f"main:{source_path}", str(target_path)],
            check=True,
        )'''
new_download_file = '''    async def download_file(self, source_path: str, target_path: Path | str) -> None:
        await self._download_via_exec(source_path, target_path, is_dir=False)'''

old_download_dir = '''        await self._chown_to_host_user(source_dir, recursive=True, service=service)
        await self._run_docker_compose_command(
            ["cp", f"{service}:{source_dir}/.", str(target_dir)],
            check=True,
        )'''
new_download_dir = '''        await self._download_via_exec(source_dir, target_dir, is_dir=True, service=service)'''

if "_download_via_exec" not in s:
    assert old_download_file in s
    assert old_download_dir in s
    s = s.replace(old_download_file, helper.replace("    async def download_file", "").rstrip() + "\n\n" + new_download_file, 1)
    s = s.replace(old_download_dir, new_download_dir, 1)
    open(p, "w").write(s)
    print("download patch applied")
else:
    print("download patch already applied")
PY
```

### C) Pass `--sandbox-user ''` to `bench eval run`

BenchFlow defaults to running the agent inside the container as user
`agent`. Creating that user requires `useradd -m` which needs UIDs we
don't have. Run as root instead:

```bash
bench eval run --sandbox-user '' ...   # NOTE the empty string
```

If you're driving bench through cap-evolve, the adapter should read
`SKILLSBENCH_SANDBOX_USER` from `.env` and pass it through:

```bash
# .env
SKILLSBENCH_SANDBOX_USER=
```

---

## Verification: run the smoke

```bash
# Set up
source <path-to-cap-evolve>/scripts/ccc/setup_podman.sh

# From your intake worktree (or any dir with a valid .env)
cd .../intake_skillbench_c1
set -a; source ./.env; set +a

# One task, one rollout — takes ~4 min
rm -rf /tmp/skillsbench-smoke-claude
bench eval run \
  --tasks-dir "$SKILLSBENCH_TASKS_DIR" \
  --include offer-letter-generator \
  --agent claude-agent-acp --model claude-opus-4-6 \
  --sandbox docker \
  --sandbox-user '' \
  --skill-mode with-skill \
  --skills-dir "$PWD/.capevolve/project/seed_capability" \
  --jobs-dir /tmp/skillsbench-smoke-claude \
  --agent-env "ANTHROPIC_BASE_URL=${ANTHROPIC_BASE_URL:?}" \
  --agent-env "ANTHROPIC_AUTH_TOKEN=${ANTHROPIC_AUTH_TOKEN:?}"
```

Success looks like:

```
✓ 1 passed   ✗ 0 failed   ⚠ 0 errored
```

or

```
✓ 0 passed   ✗ 1 failed   ⚠ 0 errored
```

Both mean the plumbing works. `failed` just means the agent's output
didn't match the verifier's expectation on this particular task — the
whole stack (container, agent install, agent execution, verifier)
worked end-to-end.

`errored: 1` means one of the workarounds above is missing. See the
troubleshooting table.

---

## Troubleshooting: which layer failed?

Read the failing rollout's `result.json` under `/tmp/skillsbench-smoke-*/
<timestamp>/<task>__<hash>/result.json`. The `error` field is verbose;
match against these patterns:

| Error contains | Which workaround failed |
|---|---|
| `insufficient UIDs or GIDs available in user namespace` at image unpack | Storage's `ignore_chown_errors` — check `~/.config/containers/storage.conf`. |
| `setuid 42 failed` / `Method http has died` during `apt-get install` | Patched ubuntu:24.04 not present — check `podman images` for it, or re-source `setup_podman.sh`. |
| `libc-devtools ... dependency problems` | `--no-install-recommends` in the patched image; re-check the image's `/etc/apt/apt.conf.d/00-rootless`. |
| `Errors were encountered while processing: fontconfig-config / libcairo2 / poppler-utils / ...` | chown/chgrp wrapper not present in the patched base — rebuild with `podman rmi -f docker.io/library/ubuntu:24.04 && rm /tmp/podman-<UID>/.patched-ubuntu24-* && source setup_podman.sh`. Verify with `podman run --rm docker.io/library/ubuntu:24.04 chown nobody:nobody /tmp && echo ok`. |
| `dpkg-statoverride: error: error setting ownership of ... : Invalid argument` (dbus/libpam-systemd/gnumeric/libgtk/libgoffice/libreoffice cascade) | `dpkg-statoverride` wrapper not present in patched base — this is the v5 fix. Rebuild the patched base (same recipe as above; setup_podman.sh v4+ includes the wrapper). Verify with `podman run --rm docker.io/library/ubuntu:24.04 head -2 /usr/bin/dpkg-statoverride` — should print `#!/bin/sh` + the swallow-error line. |
| `aardvark-dns failed to start ... systemd1` | `network_mode: host` patch (§A above) not applied to base compose yaml. |
| `Failed to connect to bus` | dbus-daemon not running — check `pgrep dbus-daemon`. |
| `readonly database` | Zombie podman services — `pkill -f 'podman system service'` and re-source. |
| `copier: put: error setting ownership of ... to 561567:...` | Upload patch (§B) not applied. |
| `chown: changing ownership of '/home/agent/.claude': Invalid argument` | `--sandbox-user ''` (§C) not passed. |
| `Agent claude-agent-acp install failed (rc=127)` with `Could not resolve host` | `network_mode: host` patch not effective — container has no network. |
| `crun: /root...` in exec | Docker-shim not on PATH — bench's stdout probe captured the "Emulate Docker CLI..." message. Check `which docker` (must be `~/.local/bin/docker`, NOT `/usr/bin/docker`). Most common cause: `~/.local/bin` was already in `$PATH` but AFTER `/usr/bin`. Fix by re-sourcing `setup_podman.sh` (v3+ prepends explicitly). |

---

## What's NOT solved

- **Task images that need to `useradd` or `chown` to arbitrary UIDs at
  runtime** will still fail. You'd hit this on any task whose Dockerfile
  installs software that assumes non-root operation (nginx, postgres, …).
  For SkillsBench (office-doc tasks), this hasn't come up.

- **Running `bench --sandbox modal` from ACP-agent tasks.** Benchflow
  0.6.5 has a bug where it dispatches Modal sandboxes through the Daytona
  process class (`sandbox.process.exec()` on Modal's Sandbox — no such
  attribute). This is a separate benchflow issue, unrelated to the CCC
  workarounds above. If you want to use Modal, you'd need to author a
  `ModalProcess` class (~200 LOC).

- **`uv tool install --force benchflow`** will wipe out patches (§A, §B).
  If you upgrade, re-apply them from this document.

---

## Sanity check: everything installed?

```bash
[ -x ~/.docker/cli-plugins/docker-compose ] && echo "compose v2: OK" || echo "compose v2: MISSING"
[ -f ~/.config/containers/containers.conf ] && echo "containers.conf: OK" || echo "containers.conf: MISSING"
[ -x ~/.local/bin/docker ] && echo "docker shim: OK" || echo "docker shim: MISSING (setup_podman.sh writes this)"
[ "$(readlink -f "$(which docker)")" = "$HOME/.local/bin/docker" ] && echo "docker shim WINS PATH: OK" || echo "docker shim SHADOWED: FAIL (/usr/bin/docker still first)"
podman images docker.io/library/ubuntu:24.04 | grep -q ubuntu && echo "patched ubuntu: OK" || echo "patched ubuntu: MISSING (setup_podman.sh builds this)"
podman run --rm docker.io/library/ubuntu:24.04 chown nobody:nobody /tmp 2>/dev/null && echo "chown wrapper: OK" || echo "chown wrapper: MISSING (rebuild patched base)"
podman run --rm docker.io/library/ubuntu:24.04 useradd _dbus 2>/dev/null && echo "useradd wrapper: OK" || echo "useradd wrapper: MISSING (rebuild patched base with v4+)"
podman run --rm docker.io/library/ubuntu:24.04 sh -c '[ -x /usr/bin/dpkg-statoverride.real ]' && echo "dpkg-statoverride wrapper: OK" || echo "dpkg-statoverride wrapper: MISSING (rebuild patched base with v5+)"
podman run --rm docker.io/library/ubuntu:24.04 sh -c 'command -v pdfinfo gcc >/dev/null' && echo "heavy preinstalls: OK" || echo "heavy preinstalls: MISSING (rebuild patched base)"
grep -q "network_mode: host" /u/$USER/.local/share/uv/tools/benchflow/lib/python*/site-packages/benchflow/sandbox/_compose_files/docker-compose-base.yaml 2>/dev/null && echo "bench yaml patch (§A): OK" || echo "bench yaml patch (§A): MISSING"
grep -q "_upload_via_exec" /u/$USER/.local/share/uv/tools/benchflow/lib/python*/site-packages/benchflow/sandbox/docker.py 2>/dev/null && echo "bench upload patch (§B): OK" || echo "bench upload patch (§B): MISSING"
grep -q "_download_via_exec" /u/$USER/.local/share/uv/tools/benchflow/lib/python*/site-packages/benchflow/sandbox/docker.py 2>/dev/null && echo "bench download patch (§B): OK" || echo "bench download patch (§B): MISSING"
```

If any prints MISSING or FAIL, re-run the corresponding step above. The
`docker shim WINS PATH` line is a common gotcha: the file can exist but
be shadowed by an earlier PATH entry — that's a rebuild-the-baseline
disaster.

---

## Batch (LSF) mode — TODO

Running the cap-evolve baseline through `bsub` on CCC needs one more
consideration: the interactive-shell setup we just did (source
`setup_podman.sh` and start dbus/podman services) needs to be part of
the batch job's environment. Draft plan (untested):

1. Wrap the workload in a shell script that sources `setup_podman.sh`
   first, then runs `cap-evolve run ...`.
2. `bsub` with enough disk on `/tmp` for the image cache (~200 MB for
   ubuntu:24.04 + task images), enough memory for concurrent rollouts
   (~4 GB × concurrency), and enough wall time (7-iter run is 4-6h).
3. LSF may kill the podman service on job teardown; if that leaves
   half-written state in `/tmp`, `setup_podman.sh` should handle the
   next run's cleanup, but verify.
4. `DOCKER_HOST` and `DBUS_SESSION_BUS_ADDRESS` are per-user paths in
   `$XDG_RUNTIME_DIR` (host-local `/tmp`) — safe.

Detailed instructions will follow after we've done a batch dry-run.
