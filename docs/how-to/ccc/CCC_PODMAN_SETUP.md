# Running Docker/Podman-based benchmarks on CCC (no admin)

**Audience:** IBM CCC users who want to run tools that assume `docker` +
`docker compose` v2, on a locked-down cluster where you have no root, no
`sudo`, no `/etc/subuid` entry, and (on compute nodes) no systemd user
session. This document is a walkthrough of the exact set of userspace
workarounds we found through trial and error while getting BenchFlow +
SkillsBench + Claude Code running for the `cap-evolve` project. Every step
is reproducible without admin help.

**Written:** 2026-07-29. **Updated:** 2026-08-21 with these iterative
fixes (each caught a specific class of failing task):
- v2 → v3: `chown`/`chgrp` wrappers (postinst chown failures)
- v3 → v4: `useradd`/`groupadd`/`usermod`/`groupmod`/`adduser`/`addgroup`
  wrappers (packages that create system users)
- v4 → v5: `dpkg-statoverride` wrapper (dbus's setuid-helper ownership
  fix, and everything downstream — libpam-systemd, gnumeric, libgtk,
  libgoffice, libreoffice)
- v5 → v6 → v7 (2026-08-21): pre-install `uv`/`uvx` at BOTH `/usr/local/bin`
  AND `/root/.local/bin` at build time, plus `TAR_OPTIONS=--no-same-owner`.
  Unblocks 8+ SkillsBench tasks whose verifier scripts hardcode
  `source $HOME/.local/bin/env && uvx ...` — their `curl | sh` install
  fails silently on compute nodes (either no outbound access to
  astral.sh, or `tar` hits `Cannot change ownership to uid 1001, gid 117`
  under rootless podman single-UID user namespace). Baking uv into the
  image at both paths satisfies the verifier's hardcoded expectations
  without needing test-time network access.
- PATH-ordering fix so our `docker` shim isn't shadowed by
  `/usr/bin/docker`
- `poppler-utils` + `build-essential` + `ca-certificates` preinstalled
  in the base image

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
source scripts/ccc/setup_podman.sh   # one line
docker run --rm ubuntu:24.04 uname -a                              # works
docker compose -f your.yaml up -d                                  # works
bench eval run --sandbox docker ...                                # works
```

with no admin help. The setup script is idempotent — sourcing it again in
another shell is a no-op.

---

## Prerequisites

- CCC account with home in `/u/<user>` and access to `/dccstor/...` for
  shared data.
- A checkout of this repo. The setup script ships with it at
  [`scripts/ccc/setup_podman.sh`](../../../scripts/ccc/setup_podman.sh) —
  every path below is relative to the repo root. If you keep a patched
  copy elsewhere, point `$CCC_SETUP_PODMAN` at it and the runner scripts
  will use that instead.
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
source scripts/ccc/setup_podman.sh
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

> **⚠ Not yet wired for the cap-evolve path.** This works when you call
> `bench` directly — which is why `run_ccc_smoke.sh` passes
> `--sandbox-user ''` and passes. It does **not** yet work through
> cap-evolve: `examples/skillsbench/adapters/adapter.py` never passes
> `--sandbox-user`, and nothing in the repo reads
> `SKILLSBENCH_SANDBOX_USER`. So the smoke succeeds while a real
> `run_ccc_experiment.sh` run hits exactly the failure in the
> troubleshooting table below:
>
> ```
> chown: changing ownership of '/home/agent/.claude': Invalid argument
> ```
>
> Fixing it needs an adapter change that is not in `main` yet — the
> adapter should read `SKILLSBENCH_SANDBOX_USER` from `.env` and forward
> it:
>
> ```bash
> # .env
> SKILLSBENCH_SANDBOX_USER=
> ```
>
> Until that lands, don't be surprised when the smoke is green and the
> full run is not.

---

### D) Pre-install `uv`/`uvx` in the base image (SkillsBench verifier fix, 2026-08-21)

Many SkillsBench task `verifier/test.sh` scripts start with something like:

```bash
curl -LsSf https://astral.sh/uv/0.9.7/install.sh | sh > /dev/null 2>&1
source $HOME/.local/bin/env
uvx --with pytest ... pytest ...
```

On CCC compute nodes this fails silently for two independent reasons:

1. **Compute nodes may lack outbound access to `https://astral.sh`.** The
   `curl` fails, `2>/dev/null` swallows the error, `/root/.local/bin/env`
   is never created, and `source` errors with "No such file or directory".

2. **When curl works, the tar-extract still fails.** Astral's uv tarball
   embeds file entries with uid=1001/gid=117 (uv's build user). Under
   rootless podman single-UID user namespace, `tar` fails with
   `Cannot change ownership to uid 1001, gid 117: Invalid argument`.

The fix (baked into `setup_podman.sh`'s patched-ubuntu-v7 image build):

- Pre-install `uv`/`uvx` to `/usr/local/bin` (system-wide fallback).
- Pre-install `uv`/`uvx` **also** to `/root/.local/bin` (the exact path
  the verifier hardcodes via `$HOME/.local/bin/env`). This uses the
  astral installer with `HOME=/root` during the Dockerfile RUN, which
  writes uv, uvx, AND the `env` activation script.
- Set `TAR_OPTIONS=--no-same-owner` in the image env (belt-and-braces:
  if a task's verifier still tries its own install, the tar extract
  now succeeds instead of failing on chown).

Result: the verifier's `curl | sh` becomes a no-op (or succeeds via
TAR_OPTIONS), `source $HOME/.local/bin/env` finds the pre-baked script,
and `uvx --with pytest ...` runs normally.

**Confirmed 2026-08-21:** `offer-letter-generator` went from "0/10 seed
(infra fail)" to "10/10 seed (actually saturated)" once the v7 image was
used. Same fix expected to unblock 7 other SkillsBench tasks whose
verifiers hardcode the same `uvx` pattern.

## Verification: run the smoke

```bash
# Set up
source scripts/ccc/setup_podman.sh

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

## Layer index: symptom → fix

Thirteen distinct failures had to be resolved to get one task to run, each
one hidden behind the last. This is the scannable index; the sections
above have the detail and the reproduction commands.

| # | Symptom | Fix | Where |
|---|---|---|---|
| 1 | Image unpack fails, `lchown /etc/gshadow` | `ignore_chown_errors = "true"` | `storage.conf` |
| 2 | `apt-get install` fails setuid to `_apt` (UID 42) | `APT::Sandbox::User "root";` | patched base |
| 3 | Postinst chowns in `libc-devtools`/`libgd3`/`fontconfig-config` | `APT::Install-Recommends "false";` + pre-install `python3 python3-pip curl` | patched base |
| 4 | `aardvark-dns: Failed to connect to bus` | private `dbus-daemon --session`; `containers.conf` disables systemd/cgroup paths | `setup_podman.sh` |
| 5 | `aardvark-dns: Failed to start transient scope unit` (no systemd) | `network_mode: host` in the base compose yaml | §A |
| 6 | `readonly database` from zombie podman services | idempotent start (pkill + pidfile) | `setup_podman.sh` |
| 7 | `docker compose cp` chowns to host UIDs absent from the namespace | replace upload/download with `exec -T` + tar streams | §B |
| 8 | `docker compose exec` insists on the `agent` user | `--sandbox-user ''` | §C ⚠ |
| 9 | `Emulate Docker CLI using podman` polluting bench's `pwd` probe | userspace `docker` shim execing podman | `setup_podman.sh` |
| 10 | Shim shadowed by `/usr/bin/docker` | explicitly PREPEND `~/.local/bin` to `PATH` | `setup_podman.sh` |
| 11 | Postinst chowns (fontconfig/poppler/cairo) | wrap `chown`/`chgrp`; pre-install `poppler-utils`, `build-essential` | patched base v3 |
| 12 | Postinst creates system users (`_dbus`, `messagebus`) | wrap `useradd`/`groupadd`/`usermod`/`groupmod`/`adduser`/`addgroup` | patched base v4 |
| 13 | `dpkg-statoverride` `fchown()` → hard dpkg error, cascading through libpam-systemd/gnumeric/libgtk/libgoffice/libreoffice | wrap `dpkg-statoverride` | patched base v5 |

Removing any one of these puts the smoke back to failing. ⚠ Layer 8 is
**not** wired for the cap-evolve path — see §C.

---

## What this touches outside the repo

Everything the setup writes to, so you know your own blast radius. All of
it is in `$HOME` or host-local `/tmp`; nothing needs root.

| Path | What | Written by |
|---|---|---|
| `~/.config/containers/storage.conf` | `graphroot`/`runroot` + `ignore_chown_errors` | `setup_podman.sh` (backs up an existing file once to `.bak`) |
| `~/.config/containers/containers.conf` | compose provider, disables systemd/dbus paths | you, by hand (one-time setup §2) |
| `~/.docker/cli-plugins/docker-compose` | Compose v2 binary (~60 MB) | you, by hand (one-time setup §1) |
| `~/.local/bin/docker` | shim execing podman | `setup_podman.sh` |
| `/tmp/podman-<UID>/`, `/tmp/podman-run-<UID>/` | image store, sockets, dbus, pidfiles | `setup_podman.sh`, per host |
| `docker.io/library/ubuntu:24.04` | **replaced** with the patched base | `setup_podman.sh` — see the blast-radius section |
| benchflow's `site-packages` | `docker-compose-base.yaml` (§A), `docker.py` (§B) | you, by hand; originals kept as `.orig` |

The benchflow edits are wiped by `uv tool install --force benchflow`; re-apply
§A and §B after any upgrade.

### If you ever get admin help, delete all of it

Every workaround here exists to route around one missing thing: a subuid
range. If CCC admins add you to `/etc/subuid` and `/etc/subgid`, then
`setup_podman.sh`'s image patching, the wrappers, `ignore_chown_errors`,
and the §A/§B benchflow edits all become unnecessary — a normal rootless
podman setup would just work. Revisit this document as a whole rather
than maintaining it indefinitely.

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

## Blast radius: we shadow the official `ubuntu:24.04` tag

**Read this before running `setup_podman.sh` on a node you share with
other projects.** The patched base image is built and tagged as
`docker.io/library/ubuntu:24.04` — the *upstream* tag — after a
`podman rmi -f` on whatever was cached there. Consequences:

- **Any other project on that node that builds `FROM ubuntu:24.04` gets
  our mutated base**, silently. Their `chown`/`useradd`/`dpkg-statoverride`
  become wrappers, and `/etc/environment` carries
  `TAR_OPTIONS=--no-same-owner`.
- **Those wrappers swallow every error, not just the `EINVAL` we're
  working around** (`2>/dev/null || :`). A genuine permission bug inside a
  task image now passes silently, which can turn a real failure into a
  wrong-but-green verifier result. That is a **benchmark-integrity** risk,
  not just a convenience one — if a task's scoring depends on file
  ownership, treat its result as suspect.
- **Your pristine cached upstream image is destroyed** by the `rmi -f`.

Why tag-shadowing rather than a private tag: task images come from
SkillsBench with `FROM ubuntu:24.04` baked in, and we can't rewrite every
upstream Dockerfile. A private tag (`localhost/ccc-ubuntu:24.04`) would
keep the blast radius inside this project, and is the right fix if
benchflow ever grows a base-image override. Until then this is a
deliberate, and deliberately loud, trade-off.

### How to revert

```bash
# Drop the patched image and the build marker, then re-pull upstream.
podman rmi -f docker.io/library/ubuntu:24.04
rm -f /tmp/podman-$(id -u)/.patched-ubuntu24-v*
podman pull docker.io/library/ubuntu:24.04
```

Sourcing `setup_podman.sh` again rebuilds the patched image, so revert
only in a shell where you won't re-source it.

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
[ "$(readlink -f "$(command -v docker)")" = "$(readlink -f "$HOME/.local/bin/docker")" ] && echo "docker shim WINS PATH: OK" || echo "docker shim SHADOWED: FAIL (/usr/bin/docker still first)"
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

## Batch (LSF) mode

The interactive-shell setup above (source `setup_podman.sh`, start
dbus/podman services) has to happen inside the batch job. That wrapper
is [`scripts/ccc/run_ccc_experiment.sh`](../../../scripts/ccc/run_ccc_experiment.sh):
Phase 1 sources `setup_podman.sh`, Phase 2 loads `.env`, Phase 3 runs
`cap-evolve run`, Phase 4 prints the headline summary. Results land under
`results/<suite-id>/<LSB_JOBID>/`, with `cap-evolve.log` as the
per-job transcript.

The draft plan's assumptions held up: `DOCKER_HOST` and
`DBUS_SESSION_BUS_ADDRESS` are host-local `/tmp` paths and are safe, and
`setup_podman.sh` cleans up the previous run's `/tmp` state. What did
*not* hold up is the wall-time advice — see below.

The lessons here were paid for in lost runs during the `transfer_eval_v1`
8-fold zero-shot transfer pilot (2026-09-01/02, `--max-iterations 0`).

### Do NOT pass `-W` (wall-clock limit)

Omit the flag entirely. This reverses the earlier draft advice to "give
it enough wall time."

A `--max-iterations 0` job finishes its actual `cap-evolve run` in
roughly 45 minutes, **then frequently fails to exit** — it hangs
indefinitely in a post-run step (dashboard/teardown) with the complete
result already written to `cap-evolve.log`. With `-W 2:00` set, LSF then
killed those jobs with `TERM_RUNLIMIT` *after the work was done*,
turning successful runs into `EXIT` and making valid results look like
failures. Several folds had to be re-run purely because of this.

`-W` cannot rescue you from the hang anyway — the hang is the bug, and a
wall-clock limit just decides how long you wait before losing the job's
exit status. Detect completion from the log instead (next section).

`submit_ccc_experiment.sh` therefore has **no walltime support at all** —
it never passes `-W` and offers no flag to add one, so the default cannot
be quietly reintroduced by a copied command line. If you hand-roll a
`bsub`, leave `-W` off yourself.

### Poll `cap-evolve.log`, not `bjobs` STAT

Because of that hang, `bjobs` STAT is **not** a reliable signal that a
job is still working. A finished job sits in `RUN` forever. The working
procedure:

```bash
log=results/<suite-id>/<jobid>/cap-evolve.log
# A complete run ends with a JSON block containing "iterations".
if grep -q '"iterations"' "$log"; then
    # work is done — the process is just hung. Kill this exact job.
    bkill <jobid>
fi
```

Kill **by exact job ID only.** Never `bkill 0` or a wildcard: several
worktrees/sessions run concurrently under the same UID, and a bulk kill
takes out someone else's in-flight jobs.

### Faster first pass: sweep every job with `lout`

Grepping each run's `cap-evolve.log` needs the suite-id and job-id paths.
To triage *all* your in-flight jobs at once, ask LSF directly instead —
`lout <jobid>` prints the job's output, and a finished job's output
contains an `Exit:` line even while `bjobs` still reports `RUN`:

```bash
for run in `bjobs | cut -d " " -f1` ; do echo $run ; lout $run | grep "Exit:     0" ; done
```

Any job that prints `Exit:     0` **has already completed** — it is a
zombie holding a dedicated host, and `bkill <that exact id>` is correct
cleanup, not an interruption. A job that prints nothing is genuinely
still working; leave it alone. (Mind the spacing in the grep: it is
`Exit:` followed by five spaces.)

Use this as the routine sweep in every status check, then fall back to
the `cap-evolve.log` check above when you need to know *what the result
was* rather than merely whether the job is done. Worked example: on
2026-09-02 job 554531 sat in `RUN` for 3+ hours after its finalize had
completed, holding a dedicated host that a queued job needed; `lout
554531` matched immediately, while a concurrent job on the same suite
printed nothing and was in fact still finalizing.

### Distinguish a hung *payload* from a hung *setup*

Two different hangs, two different responses:

| symptom | meaning | action |
|---|---|---|
| `cap-evolve.log` has a complete result JSON, job still `RUN` | payload done, post-run hang | `bkill <jobid>`, keep the result |
| no `cap-evolve.log` at all after ~45 min of `RUN`; stdout frozen in Phase 1/2 | stalled in podman/env setup, never reached `cap-evolve run` | `bkill <jobid>`, resubmit on a **different** host with a fresh `--run-ts` |

The second case is real: one fold sat in `RUN` for 15.6 hours with
stdout frozen at "Phase 2: loading .env" and never produced a log. There
is no result to salvage — resubmit. Bump `--run-ts` (e.g. `..._v3`) so
the retry doesn't resume the previous attempt's partial
`.capevolve/run_<run-ts>/` state.

### One dedicated host per concurrent job (`-m <host>`)

Rootless podman's graphroot is **per-user per-host**, not per-process, so
two of your own jobs on the same host share and corrupt each other's
container state. Pin every concurrent job to its own host:

```bash
bsub -m cccxc442 ...
```

Pick hosts that are `ok` in `bhosts -w` **and** absent from `brsvs -w` —
an advance reservation can block a host for another group even when it
looks idle.

### Do NOT submit to the `cccxc6xx` machines

**Never pin a job to a host in the `cccxc600`–`cccxc630` range.** That
entire range is held by the `infusion` advance reservation for
`grp_res_infusion`, on a time window running to 2038 — permanent for our
purposes. Jobs pinned there pend indefinitely or get bumped.

This one is a trap, because `bhosts -w` makes them look like the *best*
available choice:

```console
$ bhosts -w cccxc610 cccxc630
HOST_NAME   STATUS   JL/U  MAX  NJOBS  RUN  SSUSP  USUSP  RSV
cccxc610    ok       -     128  0      0    0      0      0
cccxc630    ok       -     128  0      0    0      0      0
```

`ok` and completely idle — and unusable. `bhosts` does not show
reservations; only `brsvs -w` does. Always cross-check there before
pinning:

```bash
brsvs -w | grep -E "cccxc<candidate>"   # any hit => pick another host
```

Other reserved hosts to avoid, as of 2026-09: `cccxc701`, `cccxc702`,
`cccxc704`, `cccxc707`, `cccxc710`, `cccxc711` (`project-prime`, `NCU`,
`jobsfromhell`), plus `cccxc535` and `cccxc575`. In practice the
`cccxc4xx`/`cccxc5xx` hosts outside that list are the safe pool — the
transfer pilot ran on `cccxc442`, `cccxc51x`, `cccxc52x`. Re-check
`brsvs -w` rather than trusting this list, since reservations change.

### `-n 1` for `--max-iterations 0` runs

Baseline and zero-shot-transfer evals are single evaluations with no
internal parallelism; `-n 4` reserves three idle slots for nothing. Use
`-n 4` only for full multi-iteration optimizer runs.

### Submitting

[`scripts/ccc/submit_ccc_experiment.sh`](../../../scripts/ccc/submit_ccc_experiment.sh)
implements all of the above: it never passes `-W` (and has no flag to add
one), defaults to `-n 1` for `--max-iterations 0` (and `-n 4` otherwise),
and takes `--host` for the dedicated-host pin.

```bash
bash scripts/ccc/submit_ccc_experiment.sh \
    --suite-id transfer_eval_v1 --max-iterations 0 \
    --spec .capevolve/<project>/capevolve.<task>.yaml \
    --project .capevolve/<project> \
    --host cccxc442
```

Add `--dry-run` to print the `bsub` line without submitting. Override the
LSF log directory with `$CCC_LOGS` (default:
`$PROJECT_ROOT/results/.ccc_logs`).

One job per host, so a batch of N folds means N distinct `--host` values
picked per the rules above.

Also note `run_ccc_experiment.sh` resolves the CLI as
`$PROJECT_ROOT/.venv/bin/cap-evolve` — a **worktree-local** venv, not
`$PATH` or `$CAP_EVOLVE_BIN`. A fresh worktree without its own `.venv`
fails fast with `FATAL: cap-evolve CLI not found at ...` (exit 2).
Symlinking the shared venv into the worktree is enough:

```bash
ln -s /path/to/cap-evolve/.venv <worktree>/.venv
```

### Sizing (confirmed)

`/tmp` needs ~200 MB for the image cache (ubuntu:24.04 + task images);
memory ~4 GB × rollout concurrency, and `-M 64G` has been comfortable
for these runs.
