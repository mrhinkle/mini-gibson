from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.prepare_qualification_materials import (
    AstFingerprinter,
    GitHubResolver,
    ImageResolver,
    QualificationPreparationError,
    _tar_bytes,
    parse_patch_hunks,
)
from evaluation.verify_rebench import load_pinned_parser_bytes


def patch(path: str = "src/fix.py") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,3 +1,3 @@\n"
        " def fix():\n"
        "-    return 1\n"
        "+    return 2\n"
        " # end\n"
    )


class FakeNode:
    type = "function_definition"
    start_byte = 0
    parent = None
    named_children = ()

    def __init__(self, end_byte: int) -> None:
        self.end_byte = end_byte

    def named_descendant_for_point_range(self, _start, _end):
        return self

    def child_by_field_name(self, _name):
        return None


class FakeParser:
    def parse(self, source: bytes):
        return type("Tree", (), {"root_node": FakeNode(len(source))})()


def test_patch_hunks_reconstruct_exact_before_and_after_fragments() -> None:
    hunks = parse_patch_hunks(patch())
    assert len(hunks) == 1
    assert hunks[0].before == "def fix():\n    return 1\n# end\n"
    assert hunks[0].after == "def fix():\n    return 2\n# end\n"
    assert hunks[0].before_changed_rows == (1,)
    assert hunks[0].after_changed_rows == (1,)


def test_ast_fingerprints_bind_before_and_after_source() -> None:
    edits = AstFingerprinter(lambda _language: FakeParser()).edits(patch(), "python")
    assert edits == sorted(
        edits, key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":"))
    )
    assert len(edits) == 1
    assert edits[0]["path"] == "src/fix.py"
    assert edits[0]["operation"] == "update"
    assert edits[0]["node_type"] == "function_definition"
    assert edits[0]["before_sha256"] != edits[0]["after_sha256"]


def test_ast_fingerprints_cover_both_sides_of_content_rename() -> None:
    rename = (
        "diff --git a/src/old.py b/src/new.py\n"
        "similarity index 80%\n"
        "rename from src/old.py\n"
        "rename to src/new.py\n"
        "--- a/src/old.py\n"
        "+++ b/src/new.py\n"
        "@@ -1,2 +1 @@\n"
        "-old = 1\n"
        " keep = 2\n"
    )
    edits = AstFingerprinter(lambda _language: FakeParser()).edits(rename, "python")
    assert {(item["path"], item["operation"]) for item in edits} == {
        ("src/old.py", "delete"),
        ("src/new.py", "add"),
    }


def test_github_merge_commits_are_batched_and_reused_from_cache(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(command):
        calls.append(list(command))
        assert "graphql" in command
        return json.dumps(
            {
                "data": {
                    "r0": {
                        "nameWithOwner": "Owner/One",
                        "pullRequest": {
                            "number": 1,
                            "url": "https://github.com/Owner/One/pull/1",
                            "merged": True,
                            "mergeCommit": {"oid": "a" * 40},
                        },
                    },
                    "r1": {
                        "nameWithOwner": "Owner/Two",
                        "pullRequest": {
                            "number": 2,
                            "url": "https://github.com/Owner/Two/pull/2",
                            "merged": True,
                            "mergeCommit": {"oid": "b" * 40},
                        },
                    },
                }
            }
        )

    candidates = [
        {
            "instance_id": "owner__one-1",
            "repo": "Owner/One",
            "source_pr_number": 1,
            "source_pr_url": "https://github.com/Owner/One/pull/1",
        },
        {
            "instance_id": "owner__two-2",
            "repo": "Owner/Two",
            "source_pr_number": 2,
            "source_pr_url": "https://github.com/Owner/Two/pull/2",
        },
    ]
    first = GitHubResolver(tmp_path, max_new_requests=1, runner=runner)
    assert first.merge_commits(candidates) == {
        "owner__one-1": "a" * 40,
        "owner__two-2": "b" * 40,
    }
    assert first.new_requests == len(calls) == 1
    resumed = GitHubResolver(
        tmp_path,
        max_new_requests=0,
        runner=lambda _command: pytest.fail("resume ignored GitHub cache"),
    )
    assert resumed.merge_commits(candidates) == first.merge_commits(candidates)


def test_image_metadata_resolution_uses_no_pull_and_is_resumable(
    tmp_path: Path,
) -> None:
    digest = "sha256:" + "c" * 64
    calls: list[list[str]] = []

    def runner(command):
        calls.append(list(command))
        assert "pull" not in command
        return json.dumps(
            {
                "manifest": {
                    "digest": "sha256:" + "d" * 64,
                    "manifests": [
                        {
                            "digest": digest,
                            "platform": {"os": "linux", "architecture": "amd64"},
                        }
                    ],
                },
                "image": {
                    "linux/amd64": {
                        "os": "linux",
                        "architecture": "amd64",
                        "config": {"WorkingDir": "/testbed"},
                    }
                },
            }
        )

    name = "docker.io/swerebenchv2/owner-repo:1-deadbee"
    first = ImageResolver(tmp_path, max_new_resolutions=1, runner=runner)
    assert first.resolve(name)["digest"] == digest
    assert first.new_resolutions == len(calls) == 1
    resumed = ImageResolver(
        tmp_path,
        max_new_resolutions=0,
        runner=lambda _command: pytest.fail("resume ignored image cache"),
    )
    assert resumed.resolve(name)["workdir"] == "/testbed"


def test_image_root_workdir_fails_closed(tmp_path: Path) -> None:
    digest = "sha256:" + "c" * 64
    metadata = {
        "manifest": {"digest": digest},
        "image": {
            "os": "linux",
            "architecture": "amd64",
            "config": {"WorkingDir": "/"},
        },
    }
    resolver = ImageResolver(tmp_path, runner=lambda _command: json.dumps(metadata))
    with pytest.raises(QualificationPreparationError, match="workdir"):
        resolver.resolve("registry.example/owner/repo:tag")


def test_exact_upstream_style_parser_bytes_execute_with_hash_binding() -> None:
    source = b"""from lib.agent.swe_constants import TestStatus

def parse_log_pytest(output):
    return {\"case\": TestStatus.PASSED.value if output else TestStatus.FAILED.value}
"""
    digest = hashlib.sha256(source).hexdigest()
    parser = load_pinned_parser_bytes(source, "parse_log_pytest", digest)
    assert parser("ok") == {"case": "PASSED"}
    with pytest.raises(Exception, match="do not match"):
        load_pinned_parser_bytes(source + b"\n", "parse_log_pytest", digest)


def test_material_tar_is_byte_deterministic() -> None:
    manifest = {"z": 1, "a": [2, 3]}
    source = b"def parse_log_pytest(_output):\n    return {}\n"
    first = _tar_bytes(manifest, source, ["parse_log_pytest"])
    second = _tar_bytes(manifest, source, ["parse_log_pytest"])
    assert first == second
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()
