from __future__ import annotations

import re
import hashlib
import sys

import pytest

from evaluation.docker_backend import (
    DockerBackend,
    DockerIsolationError,
    DockerLimits,
    _CapturedStream,
    _ExecutionResult,
)


DIGEST = "sha256:" + "a" * 64
IMAGE = f"registry.example/rebench/task@{DIGEST}"


class RecordingBackend(DockerBackend):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[list[str], bytes, int, int]] = []

    def _execute(self, argv, stdin, timeout_s, max_output_bytes):
        self.calls.append((list(argv), stdin, timeout_s, max_output_bytes))
        return _ExecutionResult(
            0,
            _CapturedStream(
                "ok",
                hashlib.sha256(b"ok").hexdigest(),
                hashlib.sha256(b"ok").hexdigest(),
                hashlib.sha256(b"ok").hexdigest(),
                2,
                False,
            ),
            _CapturedStream(
                "",
                hashlib.sha256(b"").hexdigest(),
                hashlib.sha256(b"").hexdigest(),
                hashlib.sha256(b"").hexdigest(),
                0,
                False,
            ),
            False,
        )


def _flag_value(command: list[str], flag: str) -> str:
    return command[command.index(flag) + 1]


def test_command_enforces_hard_isolation_without_host_mounts_or_secrets() -> None:
    backend = DockerBackend(limits=DockerLimits(cpus=1.5, memory="4g", pids=128))
    command = backend.build_command(
        image=IMAGE,
        workdir="/testbed",
        command=("/bin/sh", "-lc", "true"),
        role="agent",
        container_name="mini-gibson-agent-123456abcdef",
    )

    assert command[:3] == ["docker", "run", "--rm"]
    assert _flag_value(command, "--pull") == "never"
    assert _flag_value(command, "--network") == "none"
    assert _flag_value(command, "--cap-drop") == "ALL"
    assert _flag_value(command, "--security-opt") == "no-new-privileges:true"
    assert _flag_value(command, "--user") == "1000:1000"
    assert "HOME=/tmp/home" in command
    assert _flag_value(command, "--cpus") == "1.5"
    assert _flag_value(command, "--memory") == "4g"
    assert _flag_value(command, "--memory-swap") == "4g"
    assert _flag_value(command, "--pids-limit") == "128"
    assert _flag_value(command, "--workdir") == "/testbed"
    assert command.count("--tmpfs") == 2
    assert "--volume" not in command
    assert "-v" not in command
    assert "--mount" not in command
    rendered = "\0".join(command).casefold()
    for forbidden in ("docker.sock", "/users/", "/home/", "aws_secret", "hf_token", "ssh_auth_sock"):
        assert forbidden not in rendered


def test_verifier_uses_pinned_image_user_without_weakening_isolation() -> None:
    backend = DockerBackend()
    command = backend.build_command(
        image=IMAGE,
        workdir="/testbed",
        command=("true",),
        role="verifier",
        container_name="mini-gibson-verifier-123456abcdef",
    )

    assert "--user" not in command
    assert "HOME=/tmp/home" not in command
    assert _flag_value(command, "--network") == "none"
    assert _flag_value(command, "--cap-drop") == "ALL"
    assert _flag_value(command, "--security-opt") == "no-new-privileges:true"
    assert "--volume" not in command
    assert "--mount" not in command


@pytest.mark.parametrize(
    "image",
    [
        "registry.example/task:latest",
        "registry.example/task@sha256:1234",
        f"registry.example/task@{DIGEST.upper()}",
        f"registry.example/task@{DIGEST} extra",
        f"--evil@{DIGEST}",
    ],
)
def test_mutable_or_malformed_images_are_rejected(image: str) -> None:
    backend = DockerBackend()
    with pytest.raises(DockerIsolationError, match="immutable"):
        backend.build_command(
            image=image,
            workdir="/testbed",
            command=("true",),
            role="verifier",
            container_name="mini-gibson-verifier-123456abcdef",
        )


@pytest.mark.parametrize("user", ["0", "0:0", "root", "1000:0", "-1:1000"])
def test_root_or_symbolic_users_are_rejected(user: str) -> None:
    with pytest.raises(DockerIsolationError, match="non-root"):
        DockerBackend(limits=DockerLimits(user=user))


def test_each_run_gets_a_fresh_role_scoped_container_name() -> None:
    backend = RecordingBackend()
    first = backend.run_verifier(
        image=IMAGE,
        workdir="/testbed",
        command=("true",),
        stdin=b"sealed",
        timeout_s=12,
    )
    second = backend.run_verifier(
        image=IMAGE,
        workdir="/testbed",
        command=("true",),
        stdin=b"sealed",
        timeout_s=12,
    )
    agent = backend.run_agent(image=IMAGE, workdir="/testbed", command=("true",))

    assert first.container_name != second.container_name
    assert re.fullmatch(r"mini-gibson-verifier-[0-9a-f]{12}", first.container_name)
    assert re.fullmatch(r"mini-gibson-agent-[0-9a-f]{12}", agent.container_name)
    assert all(call[1] == b"sealed" for call in backend.calls[:2])
    assert backend.calls[2][1] == b""


def test_invalid_workdir_timeout_and_role_fail_before_docker() -> None:
    backend = RecordingBackend()
    with pytest.raises(DockerIsolationError, match="workdir"):
        backend.run_verifier(
            image=IMAGE,
            workdir="/",
            command=("true",),
            stdin=b"",
            timeout_s=1,
        )
    with pytest.raises(DockerIsolationError, match="timeout"):
        backend.run(
            image=IMAGE,
            workdir="/testbed",
            command=("true",),
            timeout_s=0,
            role="agent",
        )
    with pytest.raises(DockerIsolationError, match="role"):
        backend.build_command(
            image=IMAGE,
            workdir="/testbed",
            command=("true",),
            role="other",
            container_name="mini-gibson-agent-123456abcdef",
        )
    assert backend.calls == []


def test_output_and_timeout_states_are_preserved_fail_closed() -> None:
    class TimeoutBackend(DockerBackend):
        def _execute(self, argv, stdin, timeout_s, max_output_bytes):
            return _ExecutionResult(
                -9,
                _CapturedStream(
                    "partial",
                    hashlib.sha256(b"partial").hexdigest(),
                    hashlib.sha256(b"partial").hexdigest(),
                    hashlib.sha256(b"partial").hexdigest(),
                    7,
                    True,
                ),
                _CapturedStream(
                    "deadline",
                    hashlib.sha256(b"deadline").hexdigest(),
                    hashlib.sha256(b"deadline").hexdigest(),
                    hashlib.sha256(b"deadline").hexdigest(),
                    8,
                    False,
                ),
                True,
            )

        def _remove_timed_out_container(self, name):
            self.removed = name

    backend = TimeoutBackend()
    result = backend.run_verifier(
        image=IMAGE,
        workdir="/testbed",
        command=("true",),
        stdin=b"",
        timeout_s=2,
    )
    assert result.timed_out is True
    assert result.output_truncated is True
    assert backend.removed == result.container_name


def test_execute_kills_at_host_memory_cap_without_growing_a_temp_file() -> None:
    backend = DockerBackend()
    result = backend._execute(
        [sys.executable, "-c", "import sys; sys.stdout.write('x' * 20000); sys.stdout.flush()"],
        b"",
        5,
        4096,
    )
    assert result.stdout.truncated is True
    assert result.stdout.captured_bytes == 4096
    assert result.stdout.text == "x" * 4096
    assert result.stdout.sha256 == hashlib.sha256(b"x" * 4096).hexdigest()
    assert result.stdout.head_sha256 == hashlib.sha256(b"x" * 4096).hexdigest()
    assert result.stdout.tail_sha256 == hashlib.sha256(b"x" * 4096).hexdigest()
