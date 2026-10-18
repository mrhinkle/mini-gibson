"""Small, fail-closed Docker boundary for real-repository evaluation.

The host is trusted; task images and anything executed inside them are not.  A
container launched here receives no host mounts, inherited environment, Docker
socket, or host home directory.  The caller must supply an image by immutable
digest and all input over stdin.
"""

from __future__ import annotations

import hashlib
import os
import re
import selectors
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Sequence


IMAGE_RE = re.compile(r"^(?!-)[^\s@]+@sha256:[0-9a-f]{64}$")
USER_RE = re.compile(r"^(?P<uid>[1-9][0-9]*)(?::(?P<gid>[1-9][0-9]*))?$")
MEMORY_RE = re.compile(r"^[1-9][0-9]*(?:[bkmg])$", re.I)


class DockerIsolationError(RuntimeError):
    """The requested container boundary is unsafe or could not be created."""


@dataclass(frozen=True)
class DockerLimits:
    cpus: float = 2.0
    memory: str = "8g"
    pids: int = 512
    tmpfs_size: str = "512m"
    user: str = "1000:1000"
    max_output_bytes: int = 2_000_000

    def validate(self) -> None:
        if not (0.1 <= self.cpus <= 32):
            raise DockerIsolationError("cpus must be between 0.1 and 32")
        if not MEMORY_RE.fullmatch(self.memory):
            raise DockerIsolationError("memory must be a positive Docker byte value")
        if not MEMORY_RE.fullmatch(self.tmpfs_size):
            raise DockerIsolationError("tmpfs_size must be a positive Docker byte value")
        if not (16 <= self.pids <= 4096):
            raise DockerIsolationError("pids must be between 16 and 4096")
        if not USER_RE.fullmatch(self.user):
            raise DockerIsolationError("user must be a non-root numeric uid[:gid]")
        if not (4096 <= self.max_output_bytes <= 20_000_000):
            raise DockerIsolationError("max_output_bytes is outside the safe range")


@dataclass(frozen=True)
class DockerRunResult:
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool
    output_truncated: bool
    container_name: str
    command_sha256: str
    stdout_sha256: str = ""
    stderr_sha256: str = ""
    stdout_head_sha256: str = ""
    stdout_tail_sha256: str = ""
    stderr_head_sha256: str = ""
    stderr_tail_sha256: str = ""
    stdout_captured_bytes: int = -1
    stderr_captured_bytes: int = -1

    def __post_init__(self) -> None:
        # Direct construction is useful for deterministic tests.  Production
        # execution supplies hashes over the raw captured bytes so invalid
        # UTF-8 replacement never changes the receipt evidence.
        for stream in ("stdout", "stderr"):
            raw = getattr(self, stream).encode()
            if not getattr(self, f"{stream}_sha256"):
                object.__setattr__(self, f"{stream}_sha256", hashlib.sha256(raw).hexdigest())
            if not getattr(self, f"{stream}_head_sha256"):
                object.__setattr__(
                    self,
                    f"{stream}_head_sha256",
                    hashlib.sha256(raw[:4096]).hexdigest(),
                )
            if not getattr(self, f"{stream}_tail_sha256"):
                object.__setattr__(
                    self,
                    f"{stream}_tail_sha256",
                    hashlib.sha256(raw[-4096:]).hexdigest(),
                )
            if getattr(self, f"{stream}_captured_bytes") < 0:
                object.__setattr__(self, f"{stream}_captured_bytes", len(raw))


@dataclass(frozen=True)
class _CapturedStream:
    text: str
    sha256: str
    head_sha256: str
    tail_sha256: str
    captured_bytes: int
    truncated: bool


@dataclass(frozen=True)
class _ExecutionResult:
    returncode: int | None
    stdout: _CapturedStream
    stderr: _CapturedStream
    timed_out: bool


class _StreamCollector:
    """Keep at most ``limit`` bytes while hashing a deterministic prefix."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.data = bytearray()
        self.truncated = False

    def add(self, block: bytes) -> bool:
        remaining = self.limit - len(self.data)
        if remaining > 0:
            self.data.extend(block[:remaining])
        if len(block) > remaining:
            self.truncated = True
        return self.truncated

    def finish(self) -> _CapturedStream:
        raw = bytes(self.data)
        return _CapturedStream(
            text=raw.decode("utf-8", errors="replace"),
            sha256=hashlib.sha256(raw).hexdigest(),
            head_sha256=hashlib.sha256(raw[:4096]).hexdigest(),
            tail_sha256=hashlib.sha256(raw[-4096:]).hexdigest(),
            captured_bytes=len(raw),
            truncated=self.truncated,
        )


def _validate_image(image: str) -> str:
    if not IMAGE_RE.fullmatch(image):
        raise DockerIsolationError("image must be an immutable name@sha256:<64 hex> reference")
    return image


def _validate_workdir(workdir: str) -> str:
    path = PurePosixPath(workdir)
    if not workdir.startswith("/") or workdir == "/" or ".." in path.parts:
        raise DockerIsolationError("workdir must be a safe absolute path below /")
    return workdir


def _validate_timeout(timeout_s: int) -> int:
    if isinstance(timeout_s, bool) or not isinstance(timeout_s, int) or not (1 <= timeout_s <= 1800):
        raise DockerIsolationError("timeout must be an integer between 1 and 1800 seconds")
    return timeout_s


class DockerBackend:
    """Launch one disposable, bounded container per command.

    ``run`` is intentionally stateless.  In particular, verifier calls cannot
    reuse an agent container or a previous verifier filesystem.
    """

    def __init__(self, docker: str = "docker", limits: DockerLimits | None = None) -> None:
        if not docker or any(char.isspace() for char in docker):
            raise DockerIsolationError("docker executable must be one path component")
        self.docker = docker
        self.limits = limits or DockerLimits()
        self.limits.validate()

    def build_command(
        self,
        *,
        image: str,
        workdir: str,
        command: Sequence[str],
        role: str,
        container_name: str,
    ) -> list[str]:
        _validate_image(image)
        _validate_workdir(workdir)
        if role not in {"agent", "verifier"}:
            raise DockerIsolationError("role must be agent or verifier")
        if not command or not all(isinstance(item, str) and item and "\0" not in item for item in command):
            raise DockerIsolationError("container command must be a non-empty argv")
        if not re.fullmatch(r"mini-gibson-(?:agent|verifier)-[0-9a-f]{12}", container_name):
            raise DockerIsolationError("container name was not generated by this backend")

        limits = self.limits
        # Do not add volume/mount flags or host-derived --env entries here.  The
        # absence of those flags is a security invariant asserted by tests.
        argv = [
            self.docker,
            "run",
            "--rm",
            "--pull",
            "never",
            "--name",
            container_name,
            "--platform",
            "linux/amd64",
            "--network",
            "none",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges:true",
            "--cpus",
            str(limits.cpus),
            "--memory",
            limits.memory,
            "--memory-swap",
            limits.memory,
            "--pids-limit",
            str(limits.pids),
            "--ulimit",
            "nofile=1024:1024",
            "--tmpfs",
            f"/tmp:rw,nosuid,nodev,noexec,size={limits.tmpfs_size}",
            "--tmpfs",
            " /run:rw,nosuid,nodev,noexec,size=16m".lstrip(),
            "--workdir",
            workdir,
            "--hostname",
            f"mini-gibson-{role}",
            "--env",
            "HF_HUB_OFFLINE=1",
            "--env",
            "TRANSFORMERS_OFFLINE=1",
            "--env",
            "HTTP_PROXY=",
            "--env",
            "HTTPS_PROXY=",
            "--env",
            "ALL_PROXY=",
            "--env",
            "NO_PROXY=",
            "--init",
            "-i",
        ]
        # Agent/model code remains forced to a fixed non-root identity. The
        # verifier uses the immutable image's configured user because
        # SWE-rebench images bind repository ownership, toolchains, and
        # editable installs to that identity. Verifier containers remain
        # fresh, networkless, mountless, capability-free, and no-new-privileges.
        if role == "agent":
            argv.extend(("--user", limits.user, "--env", "HOME=/tmp/home"))
        argv.extend((image, *command))
        return argv

    def run(
        self,
        *,
        image: str,
        workdir: str,
        command: Sequence[str],
        stdin: bytes = b"",
        timeout_s: int,
        role: str,
    ) -> DockerRunResult:
        _validate_timeout(timeout_s)
        suffix = uuid.uuid4().hex[:12]
        name = f"mini-gibson-{role}-{suffix}"
        argv = self.build_command(
            image=image,
            workdir=workdir,
            command=command,
            role=role,
            container_name=name,
        )
        command_sha256 = hashlib.sha256("\0".join(argv).encode()).hexdigest()
        try:
            executed = self._execute(
                argv, stdin, timeout_s, self.limits.max_output_bytes
            )
        except OSError as exc:
            raise DockerIsolationError(f"could not execute Docker: {exc}") from exc
        if executed.timed_out or executed.stdout.truncated or executed.stderr.truncated:
            self._remove_timed_out_container(name)
        return DockerRunResult(
            returncode=executed.returncode,
            stdout=executed.stdout.text,
            stderr=executed.stderr.text,
            timed_out=executed.timed_out,
            output_truncated=executed.stdout.truncated or executed.stderr.truncated,
            container_name=name,
            command_sha256=command_sha256,
            stdout_sha256=executed.stdout.sha256,
            stderr_sha256=executed.stderr.sha256,
            stdout_head_sha256=executed.stdout.head_sha256,
            stdout_tail_sha256=executed.stdout.tail_sha256,
            stderr_head_sha256=executed.stderr.head_sha256,
            stderr_tail_sha256=executed.stderr.tail_sha256,
            stdout_captured_bytes=executed.stdout.captured_bytes,
            stderr_captured_bytes=executed.stderr.captured_bytes,
        )

    def run_agent(
        self,
        *,
        image: str,
        workdir: str,
        command: Sequence[str],
        stdin: bytes = b"",
        timeout_s: int = 120,
    ) -> DockerRunResult:
        """Run one model-generated command without verifier material."""

        return self.run(
            image=image,
            workdir=workdir,
            command=command,
            stdin=stdin,
            timeout_s=timeout_s,
            role="agent",
        )

    def run_verifier(
        self,
        *,
        image: str,
        workdir: str,
        command: Sequence[str],
        stdin: bytes,
        timeout_s: int,
    ) -> DockerRunResult:
        """Run one fresh verifier container with sealed bytes supplied on stdin."""

        return self.run(
            image=image,
            workdir=workdir,
            command=command,
            stdin=stdin,
            timeout_s=timeout_s,
            role="verifier",
        )

    def _execute(
        self,
        argv: Sequence[str],
        stdin: bytes,
        timeout_s: int,
        max_output_bytes: int,
    ) -> _ExecutionResult:
        """Execute Docker with a hard in-memory output-growth boundary.

        Pipes are drained concurrently.  Once either stream exceeds its byte
        cap, Docker is killed immediately and no more output is retained.  At
        most two capped bytearrays plus OS pipe buffers exist; untrusted output
        can never grow a host file before the process exits.
        """

        host_env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")}
        process = subprocess.Popen(
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=host_env,
            bufsize=0,
        )
        if process.stdin is None or process.stdout is None or process.stderr is None:
            process.kill()
            raise DockerIsolationError("Docker pipes could not be created")

        selector = selectors.DefaultSelector()
        for pipe, label, events in (
            (process.stdout, "stdout", selectors.EVENT_READ),
            (process.stderr, "stderr", selectors.EVENT_READ),
            (process.stdin, "stdin", selectors.EVENT_WRITE),
        ):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, events, label)

        collectors = {
            "stdout": _StreamCollector(max_output_bytes),
            "stderr": _StreamCollector(max_output_bytes),
        }
        input_offset = 0
        timed_out = False
        killed_for_output = False
        deadline = time.monotonic() + timeout_s
        try:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0 and process.poll() is None:
                    timed_out = True
                    process.kill()
                events = selector.select(timeout=max(0.0, min(0.1, remaining)))
                if not events and process.poll() is not None:
                    # The pipes will report EOF on the next selector turn.
                    continue
                for key, _mask in events:
                    pipe = key.fileobj
                    label = key.data
                    if label == "stdin":
                        try:
                            if input_offset < len(stdin):
                                input_offset += os.write(pipe.fileno(), stdin[input_offset : input_offset + 65536])
                            if input_offset >= len(stdin):
                                selector.unregister(pipe)
                                pipe.close()
                        except BlockingIOError:
                            continue
                        except (BrokenPipeError, OSError):
                            selector.unregister(pipe)
                            pipe.close()
                        continue
                    try:
                        block = os.read(pipe.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not block:
                        selector.unregister(pipe)
                        pipe.close()
                        continue
                    if collectors[label].add(block) and not killed_for_output:
                        killed_for_output = True
                        if process.poll() is None:
                            process.kill()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        finally:
            selector.close()
            for pipe in (process.stdin, process.stdout, process.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
        return _ExecutionResult(
            returncode=process.returncode,
            stdout=collectors["stdout"].finish(),
            stderr=collectors["stderr"].finish(),
            timed_out=timed_out,
        )

    def _remove_timed_out_container(self, name: str) -> None:
        # This targets only the random name created by this backend.  Cleanup is
        # best-effort; the timeout result remains fail-closed if Docker is gone.
        try:
            subprocess.run(
                [self.docker, "rm", "-f", name],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
                env={"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin")},
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
