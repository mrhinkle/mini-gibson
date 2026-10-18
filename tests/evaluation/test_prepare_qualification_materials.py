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
            "base_commit": "1" * 40,
            "source_pr_number": 1,
            "source_pr_url": "https://github.com/Owner/One/pull/1",
        },
        {
            "instance_id": "owner__two-2",
            "repo": "Owner/Two",
            "base_commit": "2" * 40,
            "source_pr_number": 2,
            "source_pr_url": "https://github.com/Owner/Two/pull/2",
        },
    ]
    records = {
        candidate["instance_id"]: {
            "base_commit": candidate["base_commit"],
            "patch": patch(f"src/{candidate['source_pr_number']}.py"),
            "test_patch": patch(f"tests/test_{candidate['source_pr_number']}.py"),
        }
        for candidate in candidates
    }
    first = GitHubResolver(tmp_path, max_new_requests=1, runner=runner)
    assert first.merge_commits(candidates, records) == {
        "owner__one-1": "a" * 40,
        "owner__two-2": "b" * 40,
    }
    assert first.new_requests == len(calls) == 1
    resumed = GitHubResolver(
        tmp_path,
        max_new_requests=0,
        runner=lambda _command: pytest.fail("resume ignored GitHub cache"),
    )
    assert resumed.merge_commits(candidates, records) == first.merge_commits(
        candidates, records
    )


def test_github_merge_commit_accepts_only_verified_repository_rename(
    tmp_path: Path,
) -> None:
    candidate = {
        "instance_id": "owner__old-8",
        "repo": "Owner/Old",
        "base_commit": "1" * 40,
        "source_pr_number": 8,
        "source_pr_url": "https://github.com/Owner/New/pull/8",
    }
    record = {
        "base_commit": candidate["base_commit"],
        "patch": patch(),
        "test_patch": "",
    }

    def response(source_url: str) -> str:
        return json.dumps(
            {
                "data": {
                    "r0": {
                        "nameWithOwner": "Owner/New",
                        "pullRequest": {
                            "number": 8,
                            "url": source_url,
                            "merged": True,
                            "mergeCommit": {"oid": "d" * 40},
                        },
                    }
                }
            }
        )

    resolver = GitHubResolver(
        tmp_path / "accepted",
        max_new_requests=1,
        runner=lambda _command: response(candidate["source_pr_url"]),
    )
    assert resolver.merge_commits([candidate], {candidate["instance_id"]: record}) == {
        candidate["instance_id"]: "d" * 40
    }

    rejected = dict(candidate)
    rejected["source_pr_url"] = "https://github.com/Owner/Unrelated/pull/8"
    resolver = GitHubResolver(
        tmp_path / "rejected",
        max_new_requests=1,
        runner=lambda _command: response("https://github.com/Owner/New/pull/8"),
    )
    with pytest.raises(
        QualificationPreparationError, match="both requested and canonical"
    ):
        resolver.merge_commits([rejected], {candidate["instance_id"]: record})


def fallback_candidate() -> tuple[dict, dict]:
    candidate = {
        "instance_id": "owner__repo-7",
        "repo": "Owner/Repo",
        "base_commit": "1" * 40,
        "source_pr_number": 7,
        "source_pr_url": "https://github.com/Owner/Repo/pull/7",
    }
    record = {
        "base_commit": candidate["base_commit"],
        "patch": patch("src/fix.py"),
        "test_patch": patch("tests/test_fix.py"),
    }
    return candidate, record


def fallback_runner(*, search_items=None, authoritative_diff=None, ancestry=True):
    candidate, record = fallback_candidate()
    merge = "a" * 40
    branch = "b" * 40
    message = "Merge pull request #7 from contributor/fix-seven\n\nFix seven"
    if search_items is None:
        search_items = [{"sha": merge, "commit": {"message": message}}]
    if authoritative_diff is None:
        authoritative_diff = record["patch"] + record["test_patch"]

    def runner(command):
        rendered = " ".join(command)
        if "graphql" in command:
            return json.dumps(
                {
                    "data": {
                        "r0": {"nameWithOwner": "Owner/Repo", "pullRequest": None}
                    },
                    "errors": [
                        {
                            "type": "NOT_FOUND",
                            "path": ["r0", "pullRequest"],
                            "message": "missing",
                        }
                    ],
                }
            )
        if "search/commits" in command:
            return json.dumps(
                {
                    "total_count": len(search_items),
                    "incomplete_results": False,
                    "items": search_items,
                }
            )
        if f"commits/{merge}" in rendered:
            return json.dumps(
                {
                    "sha": merge,
                    "commit": {"message": message},
                    "parents": [{"sha": "c" * 40}, {"sha": branch}],
                }
            )
        if "Accept: application/vnd.github.v3.diff" in rendered:
            return authoritative_diff
        if "/compare/" in rendered:
            base = candidate["base_commit"]
            return json.dumps(
                {
                    "status": "ahead" if ancestry else "diverged",
                    "base_commit": {"sha": base},
                    "merge_base_commit": {"sha": base if ancestry else "d" * 40},
                    "commits": [{"sha": branch}],
                    "total_commits": 1,
                }
            )
        pytest.fail(f"unexpected command: {command}")

    return runner


def test_missing_pr_fallback_binds_exact_merge_topology_ancestry_and_diff(
    tmp_path: Path,
) -> None:
    candidate, record = fallback_candidate()
    resolver = GitHubResolver(tmp_path, max_new_requests=5, runner=fallback_runner())
    assert resolver.merge_commits([candidate], {candidate["instance_id"]: record}) == {
        candidate["instance_id"]: "a" * 40
    }
    cached = json.loads(resolver._cache_path(candidate["repo"], 7).read_text())
    assert cached["method"] == "merge_history_fallback"
    assert cached["evidence"]["parents"] == ["c" * 40, "b" * 40]
    resumed = GitHubResolver(
        tmp_path,
        max_new_requests=0,
        runner=lambda _command: pytest.fail("resume ignored fallback cache"),
    )
    assert resumed.merge_commits([candidate], {candidate["instance_id"]: record}) == {
        candidate["instance_id"]: "a" * 40
    }


@pytest.mark.parametrize("failure", ["missing", "ambiguous", "patch-mismatch"])
def test_missing_pr_fallback_rejects_unproven_history(
    tmp_path: Path,
    failure: str,
) -> None:
    candidate, record = fallback_candidate()
    message = "Merge pull request #7 from contributor/fix-seven\n\nFix seven"
    kwargs = {}
    if failure == "missing":
        kwargs["search_items"] = []
    elif failure == "ambiguous":
        kwargs["search_items"] = [
            {"sha": "a" * 40, "commit": {"message": message}},
            {"sha": "e" * 40, "commit": {"message": message}},
        ]
    else:
        kwargs["authoritative_diff"] = patch("src/not-the-frozen-patch.py")
    resolver = GitHubResolver(
        tmp_path,
        max_new_requests=5,
        runner=fallback_runner(**kwargs),
    )
    expected = (
        "missing or ambiguous" if failure != "patch-mismatch" else "does not match"
    )
    with pytest.raises(QualificationPreparationError, match=expected):
        resolver.merge_commits([candidate], {candidate["instance_id"]: record})


def transfer_candidate() -> tuple[dict, dict]:
    candidate = {
        "instance_id": "old-owner__repo-8",
        "repo": "Old-Owner/Repo",
        "base_commit": "1" * 40,
        "source_pr_number": 8,
        "source_pr_url": "https://github.com/Old-Owner/Repo/pull/8",
    }
    record = {
        "base_commit": candidate["base_commit"],
        "patch": patch("src/transferred.py"),
        "test_patch": patch("tests/test_transferred.py"),
    }
    return candidate, record


def transfer_runner(
    *,
    repositories=None,
    base_commit=None,
    authoritative_diff=None,
    incomplete=False,
):
    candidate, record = transfer_candidate()
    if repositories is None:
        repositories = ["New-Owner/Repo"]
    if base_commit is None:
        base_commit = candidate["base_commit"]
    if authoritative_diff is None:
        authoritative_diff = record["patch"] + record["test_patch"]

    def runner(command):
        rendered = " ".join(command)
        if "graphql" in command and "r0:repository" in rendered:
            return json.dumps(
                {
                    "data": {"r0": None},
                    "errors": [
                        {
                            "type": "NOT_FOUND",
                            "path": ["r0"],
                            "message": "repository missing",
                        }
                    ],
                }
            )
        if "search/commits" in command:
            items = [
                {
                    "sha": candidate["base_commit"],
                    "repository": {"full_name": repository},
                }
                for repository in repositories
            ]
            return json.dumps(
                {
                    "total_count": len(items),
                    "incomplete_results": incomplete,
                    "items": items,
                }
            )
        if "graphql" in command and "c0:repository" in rendered:
            data = {}
            for index, repository in enumerate(repositories):
                merge = f"{index + 2:x}" * 40
                data[f"c{index}"] = {
                    "nameWithOwner": repository,
                    "pullRequest": {
                        "number": 8,
                        "url": f"https://github.com/{repository}/pull/8",
                        "merged": True,
                        "baseRefOid": base_commit,
                        "headRefOid": f"{index + 8:x}" * 40,
                        "mergeCommit": {"oid": merge},
                    },
                }
            return json.dumps({"data": data})
        if "commits/" in rendered:
            return json.dumps(
                {
                    "sha": "2" * 40,
                    "commit": {"tree": {"sha": "a" * 40}},
                    "parents": [{"sha": candidate["base_commit"]}],
                }
            )
        if "pulls/8" in rendered and "application/vnd.github.v3.diff" in rendered:
            return authoritative_diff
        pytest.fail(f"unexpected command: {command}")

    return runner


def test_missing_repository_fallback_binds_transfer_pr_base_and_diff(
    tmp_path: Path,
) -> None:
    candidate, record = transfer_candidate()
    resolver = GitHubResolver(tmp_path, max_new_requests=5, runner=transfer_runner())
    assert resolver.merge_commits([candidate], {candidate["instance_id"]: record}) == {
        candidate["instance_id"]: "2" * 40
    }
    cached = json.loads(resolver._cache_path(candidate["repo"], 8).read_text())
    assert cached["method"] == "repository_transfer_fallback"
    assert cached["canonical_repo"] == "New-Owner/Repo"
    assert cached["evidence"]["discovery_query"] == candidate["base_commit"]
    assert cached["evidence"]["discovery_complete"] is True
    assert cached["evidence"]["discovery_total"] == 1
    assert cached["evidence"]["pull_request"]["base_commit"] == candidate["base_commit"]
    assert cached["evidence"]["merge_commit"]["sha"] == "2" * 40
    resumed = GitHubResolver(
        tmp_path,
        max_new_requests=0,
        runner=lambda _command: pytest.fail("resume ignored transfer cache"),
    )
    assert resumed.merge_commits([candidate], {candidate["instance_id"]: record}) == {
        candidate["instance_id"]: "2" * 40
    }


@pytest.mark.parametrize("failure", ["ambiguous", "base-mismatch", "patch-mismatch"])
def test_missing_repository_fallback_rejects_ambiguous_or_mismatched_transfer(
    tmp_path: Path,
    failure: str,
) -> None:
    candidate, record = transfer_candidate()
    kwargs = {}
    if failure == "ambiguous":
        kwargs["repositories"] = ["New-Owner/Repo", "Other-Owner/Repo"]
    elif failure == "base-mismatch":
        kwargs["base_commit"] = "f" * 40
    else:
        kwargs["authoritative_diff"] = patch("src/not-the-frozen-patch.py")
    resolver = GitHubResolver(
        tmp_path,
        max_new_requests=5,
        runner=transfer_runner(**kwargs),
    )
    expected = {
        "ambiguous": "missing or ambiguous",
        "base-mismatch": "provenance disagrees",
        "patch-mismatch": "does not match",
    }[failure]
    with pytest.raises(QualificationPreparationError, match=expected):
        resolver.merge_commits([candidate], {candidate["instance_id"]: record})


def test_repository_transfer_fallback_requires_exact_repository_not_found(
    tmp_path: Path,
) -> None:
    candidate, record = transfer_candidate()

    def runner(command):
        assert "graphql" in command
        return json.dumps(
            {
                "data": {"r0": None},
                "errors": [
                    {
                        "type": "NOT_FOUND",
                        "path": ["r0", "pullRequest"],
                        "message": "wrong boundary",
                    }
                ],
            }
        )

    resolver = GitHubResolver(tmp_path, max_new_requests=1, runner=runner)
    with pytest.raises(QualificationPreparationError, match="no repository without"):
        resolver.merge_commits([candidate], {candidate["instance_id"]: record})


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
