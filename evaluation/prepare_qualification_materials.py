"""Build outcome-blind qualification materials for the frozen 456-task plan.

The command reads only the committed candidate plan and the exact pinned
SWE-rebench V2 Parquet.  It resolves public source and image identities through
bounded, resumable metadata caches, derives syntax-tree fingerprints from the
gold-patch hunks, and writes the two inputs required by ``qualify_candidates``.
It never imports, lists, or reads ``bench/``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

from .cohort import DATASET, DATASET_REVISION, SUPPORTED_LOG_PARSERS
from .freeze_real_cohorts import SOURCE_ROWS, SOURCE_SHA256
from .qualify_candidates import (
    DATASET_FILE,
    FROZEN_PLAN_CANONICAL_SHA256,
    FROZEN_PLAN_FILE_SHA256,
    IMAGE_LOCK_SCHEMA,
    MATERIAL_SCHEMA,
    _candidate_sequence,
    _image_repository,
    _load_selected_dataset_records,
    _read_image_lock,
    _read_material_package,
    _reject_holdout_paths,
    _sha256_file,
)
from .sequential import canonical_plan_sha256, validate_sequential_plan
from .verify_rebench import (
    HUNK_HEADER_RE,
    _diff_header_paths,
    load_pinned_parser_bytes,
    patch_paths,
)

PARSER_REPOSITORY = "SWE-rebench/SWE-rebench-V2"
PARSER_REVISION = "c71902a8cf8d2b725f63d51f199f4d3e56f68d2d"
PARSER_PATH = "lib/agent/log_parsers.py"
PARSER_BLOB_SHA1 = "51c2e178b392f36aedc3c64064a708498ff591f8"
AST_SPEC = "mini-gibson-ast-edits/v1"
SOURCE_CACHE_SCHEMA = "mini-gibson-github-source-identity-cache/v1"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
LANGUAGE_GRAMMARS = {
    "python": "python",
    "go": "go",
    "ts": "typescript",
    "rust": "rust",
    "js": "javascript",
    "java": "java",
    "julia": "julia",
    "swift": "swift",
    "php": "php",
    "scala": "scala",
    "kotlin": "kotlin",
    "elixir": "elixir",
    "r": "r",
    "dart": "dart",
    "ocaml": "ocaml",
}


class QualificationPreparationError(ValueError):
    """A source, syntax, image, or output identity cannot be sealed safely."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n"


def _git_blob_sha1(value: bytes) -> str:
    header = f"blob {len(value)}\0".encode()
    return hashlib.sha1(header + value).hexdigest()


def _canonical_patch_sections(patch: str) -> dict[str, str]:
    """Return path-keyed semantic Git diff sections with display metadata removed."""

    sections: list[list[str]] = []
    current: list[str] | None = None
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            if current is not None:
                sections.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
        elif line.strip():
            raise QualificationPreparationError(
                "patch content precedes its diff header"
            )
    if current is not None:
        sections.append(current)
    if not sections:
        raise QualificationPreparationError("patch contains no diff sections")

    result: dict[str, str] = {}
    for lines in sections:
        old_path, new_path = _diff_header_paths(lines[0])
        key = f"{old_path}\0{new_path}"
        if key in result:
            raise QualificationPreparationError(
                "patch contains duplicate path sections"
            )
        canonical = [f"diff --git a/{old_path} b/{new_path}"]
        for line in lines[1:]:
            if line.startswith("index "):
                continue
            match = HUNK_HEADER_RE.fullmatch(line)
            if match:
                old_count = int(match.group("old_count") or 1)
                new_count = int(match.group("new_count") or 1)
                canonical.append(
                    f"@@ -{int(match.group('old_start'))},{old_count} "
                    f"+{int(match.group('new_start'))},{new_count} @@"
                )
            else:
                canonical.append(line)
        result[key] = "\n".join(canonical) + "\n"
    # Reuse the verifier's strict path parser before any external diff is trusted.
    patch_paths(patch)
    return result


def _expected_patch_sections(record: Mapping[str, Any]) -> dict[str, str]:
    product = _canonical_patch_sections(record["patch"])
    test_patch = record["test_patch"]
    tests = _canonical_patch_sections(test_patch) if test_patch.strip() else {}
    overlap = set(product) & set(tests)
    if overlap:
        raise QualificationPreparationError(
            f"product and test patches overlap the same file sections: {sorted(overlap)}"
        )
    return {**product, **tests}


def _patch_sections_sha256(sections: Mapping[str, str]) -> str:
    return _sha256_bytes(
        json.dumps(sections, sort_keys=True, separators=(",", ":")).encode()
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _read_cached_json(path: Path) -> Mapping[str, Any] | None:
    if not path.exists():
        return None
    if not path.is_file() or path.is_symlink():
        raise QualificationPreparationError(
            f"cache entry is not a regular file: {path}"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationPreparationError(
            f"invalid cache entry {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise QualificationPreparationError(f"cache entry is not an object: {path}")
    return value


def _run_command(command: Sequence[str], *, timeout: int = 120) -> str:
    environment = {"PATH": os.environ.get("PATH", "")}
    executable = Path(command[0]).name
    permitted = (
        ("HOME", "GH_CONFIG_DIR", "GH_HOST", "GH_TOKEN", "GITHUB_TOKEN")
        if executable == "gh"
        else ("HOME", "DOCKER_CONFIG")
    )
    environment.update(
        {name: os.environ[name] for name in permitted if name in os.environ}
    )
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QualificationPreparationError(f"metadata command failed: {exc}") from exc
    if completed.returncode != 0:
        if "graphql" in command:
            try:
                partial = json.loads(completed.stdout)
            except json.JSONDecodeError:
                partial = None
            if (
                isinstance(partial, dict)
                and isinstance(partial.get("data"), dict)
                and isinstance(partial.get("errors"), list)
            ):
                return completed.stdout
        stderr = completed.stderr.strip().replace("\n", " ")[:500]
        raise QualificationPreparationError(
            f"metadata command exited {completed.returncode}: {stderr}"
        )
    return completed.stdout


def _validate_pr_url(url: Any, repo: str, number: int) -> None:
    if not isinstance(url, str):
        raise QualificationPreparationError(
            f"{repo}#{number}: GitHub returned no PR URL"
        )
    parsed = urlparse(url)
    parts = [part for part in parsed.path.split("/") if part]
    expected = [*repo.split("/"), "pull", str(number)]
    if (
        parsed.scheme != "https"
        or parsed.netloc.casefold() != "github.com"
        or len(parts) != 4
        or [part.casefold() for part in parts[:2]]
        != [part.casefold() for part in expected[:2]]
        or parts[2:] != expected[2:]
    ):
        raise QualificationPreparationError(
            f"{repo}#{number}: authoritative PR URL disagrees"
        )


def _validate_source_pr_url(
    url: Any,
    requested_repo: str,
    canonical_repo: str,
    number: int,
) -> None:
    """Accept only the requested or GitHub-resolved repository for a frozen URL."""

    for repo in dict.fromkeys((requested_repo, canonical_repo)):
        try:
            _validate_pr_url(url, repo, number)
        except QualificationPreparationError:
            continue
        return
    raise QualificationPreparationError(
        f"{requested_repo}#{number}: frozen source PR URL disagrees with both "
        "requested and canonical repositories"
    )


class GitHubResolver:
    """Resolve pinned parser bytes and merge commits with a bounded GH cache."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        gh: str = "gh",
        max_new_requests: int = 25,
        batch_size: int = 25,
        runner: Callable[[Sequence[str]], str] = _run_command,
    ) -> None:
        if max_new_requests < 0 or not 1 <= batch_size <= 50:
            raise QualificationPreparationError(
                "invalid GitHub request budget or batch size"
            )
        self.cache_dir = cache_dir
        self.gh = gh
        self.max_new_requests = max_new_requests
        self.batch_size = batch_size
        self.runner = runner
        self.new_requests = 0

    def _request(self, arguments: Sequence[str]) -> str:
        if self.new_requests >= self.max_new_requests:
            raise QualificationPreparationError(
                "GitHub request budget exhausted; rerun with the same cache to resume"
            )
        self.new_requests += 1
        return self.runner([self.gh, "api", *arguments])

    def parser_source(self) -> bytes:
        source_path = self.cache_dir / "github" / "pinned-log-parsers.py"
        meta_path = self.cache_dir / "github" / "pinned-log-parsers.json"
        meta = _read_cached_json(meta_path)
        if source_path.exists() or meta is not None:
            if (
                meta is None
                or not source_path.is_file()
                or source_path.is_symlink()
                or meta
                != {
                    "repository": PARSER_REPOSITORY,
                    "revision": PARSER_REVISION,
                    "path": PARSER_PATH,
                    "blob_sha1": PARSER_BLOB_SHA1,
                }
            ):
                raise QualificationPreparationError(
                    "pinned parser cache is incomplete or inconsistent"
                )
            source = source_path.read_bytes()
            if _git_blob_sha1(source) != PARSER_BLOB_SHA1:
                raise QualificationPreparationError(
                    "cached parser bytes do not match pinned Git blob"
                )
            return source

        endpoint = f"repos/{PARSER_REPOSITORY}/contents/{PARSER_PATH}"
        raw = self._request(["-X", "GET", endpoint, "-f", f"ref={PARSER_REVISION}"])
        try:
            response = json.loads(raw)
            if (
                not isinstance(response, dict)
                or response.get("sha") != PARSER_BLOB_SHA1
            ):
                raise QualificationPreparationError(
                    "GitHub parser blob identity disagrees"
                )
            source = base64.b64decode(response["content"], validate=False)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                "GitHub returned malformed parser content"
            ) from exc
        if _git_blob_sha1(source) != PARSER_BLOB_SHA1:
            raise QualificationPreparationError(
                "downloaded parser bytes do not match pinned Git blob"
            )
        _atomic_write(source_path, source)
        _atomic_write(
            meta_path,
            _canonical_bytes(
                {
                    "repository": PARSER_REPOSITORY,
                    "revision": PARSER_REVISION,
                    "path": PARSER_PATH,
                    "blob_sha1": PARSER_BLOB_SHA1,
                }
            ),
        )
        return source

    def _cache_path(self, repo: str, number: int) -> Path:
        key = hashlib.sha256(f"{repo.casefold()}#{number}".encode()).hexdigest()
        return self.cache_dir / "github" / "pulls" / f"{key}.json"

    @staticmethod
    def _record_bindings(record: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "base_commit": record["base_commit"],
            "patch_sha256": _sha256_bytes(record["patch"].encode()),
            "test_patch_sha256": _sha256_bytes(record["test_patch"].encode()),
        }

    def _store_source_cache(
        self, repo: str, number: int, value: Mapping[str, Any]
    ) -> None:
        payload = dict(value)
        payload["record_sha256"] = _sha256_bytes(_canonical_bytes(payload))
        _atomic_write(self._cache_path(repo, number), _canonical_bytes(payload))

    def _cached_source(
        self,
        candidate: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> str | None:
        repo = candidate["repo"]
        number = candidate["source_pr_number"]
        value = _read_cached_json(self._cache_path(repo, number))
        if value is None:
            return None
        record_sha = value.get("record_sha256")
        unsigned = {key: item for key, item in value.items() if key != "record_sha256"}
        if not isinstance(record_sha, str) or record_sha != _sha256_bytes(
            _canonical_bytes(unsigned)
        ):
            raise QualificationPreparationError(
                f"{repo}#{number}: GitHub evidence cache integrity failure"
            )
        expected_keys = {
            "schema_version",
            "requested_repo",
            "canonical_repo",
            "pr_number",
            "source_pr_url",
            "method",
            "merge_commit_sha",
            "record_bindings",
            "evidence",
            "record_sha256",
        }
        if (
            set(value) != expected_keys
            or value["schema_version"] != SOURCE_CACHE_SCHEMA
        ):
            raise QualificationPreparationError(
                f"{repo}#{number}: malformed GitHub evidence cache"
            )
        if (
            value["requested_repo"].casefold() != repo.casefold()
            or value["pr_number"] != number
        ):
            raise QualificationPreparationError(
                f"{repo}#{number}: GitHub evidence cache binding disagrees"
            )
        if value["source_pr_url"] != candidate["source_pr_url"]:
            raise QualificationPreparationError(
                f"{repo}#{number}: cached source URL disagrees"
            )
        if value["record_bindings"] != self._record_bindings(record):
            raise QualificationPreparationError(
                f"{repo}#{number}: cached dataset bindings disagree"
            )
        canonical_repo = value["canonical_repo"]
        if not isinstance(canonical_repo, str) or canonical_repo.count("/") != 1:
            raise QualificationPreparationError(
                f"{repo}#{number}: invalid cached canonical repository"
            )
        _validate_source_pr_url(
            candidate["source_pr_url"], repo, canonical_repo, number
        )
        merge_commit = value["merge_commit_sha"]
        if not isinstance(merge_commit, str) or not GIT_SHA_RE.fullmatch(merge_commit):
            raise QualificationPreparationError(
                f"{repo}#{number}: invalid cached merge commit"
            )
        evidence = value["evidence"]
        if not isinstance(evidence, dict):
            raise QualificationPreparationError(
                f"{repo}#{number}: malformed cached evidence"
            )
        if value["method"] == "pull_api":
            if set(evidence) != {"url", "merged"} or evidence["merged"] is not True:
                raise QualificationPreparationError(
                    f"{repo}#{number}: malformed cached PR evidence"
                )
            _validate_pr_url(evidence["url"], canonical_repo, number)
        elif value["method"] == "merge_history_fallback":
            fallback_keys = {
                "merge_message",
                "parents",
                "branch_head",
                "compare_status",
                "canonical_patch_sections_sha256",
                "authoritative_diff_sha256",
            }
            if set(evidence) != fallback_keys:
                raise QualificationPreparationError(
                    f"{repo}#{number}: malformed cached fallback evidence"
                )
            message = evidence["merge_message"]
            parents = evidence["parents"]
            if (
                not isinstance(message, str)
                or not re.fullmatch(
                    rf"Merge pull request #{number} from [^\r\n]+",
                    message.splitlines()[0],
                )
                or not isinstance(parents, list)
                or len(parents) != 2
                or not all(
                    isinstance(item, str) and GIT_SHA_RE.fullmatch(item)
                    for item in parents
                )
                or evidence["branch_head"] != parents[1]
                or evidence["compare_status"] != "ahead"
                or not SHA256_RE.fullmatch(evidence["canonical_patch_sections_sha256"])
                or evidence["canonical_patch_sections_sha256"]
                != _patch_sections_sha256(_expected_patch_sections(record))
                or not SHA256_RE.fullmatch(evidence["authoritative_diff_sha256"])
            ):
                raise QualificationPreparationError(
                    f"{repo}#{number}: invalid cached fallback provenance"
                )
        elif value["method"] == "repository_transfer_fallback":
            transfer_keys = {
                "discovery_query",
                "discovery_results",
                "discovery_complete",
                "discovery_total",
                "pull_request",
                "merge_commit",
                "canonical_patch_sections_sha256",
                "authoritative_diff_sha256",
            }
            if set(evidence) != transfer_keys:
                raise QualificationPreparationError(
                    f"{repo}#{number}: malformed cached repository-transfer evidence"
                )
            discovery_results = evidence["discovery_results"]
            pull = evidence["pull_request"]
            commit = evidence["merge_commit"]
            expected_basename = repo.rsplit("/", 1)[-1].casefold()
            if (
                evidence["discovery_query"] != record["base_commit"]
                or evidence["discovery_complete"] is not True
                or not isinstance(discovery_results, list)
                or not discovery_results
                or evidence["discovery_total"] != len(discovery_results)
                or any(
                    not isinstance(item, dict)
                    or set(item) != {"repository", "sha"}
                    or item["sha"] != record["base_commit"]
                    or not isinstance(item["repository"], str)
                    or item["repository"].count("/") != 1
                    for item in discovery_results
                )
                or not any(
                    item["repository"].casefold() == canonical_repo.casefold()
                    and item["repository"].rsplit("/", 1)[-1].casefold()
                    == expected_basename
                    for item in discovery_results
                )
                or not isinstance(pull, dict)
                or set(pull)
                != {
                    "number",
                    "url",
                    "merged",
                    "base_commit",
                    "head_commit",
                    "merge_commit",
                }
                or pull["number"] != number
                or pull["merged"] is not True
                or pull["base_commit"] != record["base_commit"]
                or not isinstance(pull["head_commit"], str)
                or not GIT_SHA_RE.fullmatch(pull["head_commit"])
                or pull["merge_commit"] != merge_commit
                or not isinstance(commit, dict)
                or set(commit) != {"sha", "tree", "parents"}
                or commit["sha"] != merge_commit
                or not isinstance(commit["tree"], str)
                or not GIT_SHA_RE.fullmatch(commit["tree"])
                or not isinstance(commit["parents"], list)
                or not commit["parents"]
                or not all(
                    isinstance(parent, str) and GIT_SHA_RE.fullmatch(parent)
                    for parent in commit["parents"]
                )
                or evidence["canonical_patch_sections_sha256"]
                != _patch_sections_sha256(_expected_patch_sections(record))
                or not SHA256_RE.fullmatch(evidence["authoritative_diff_sha256"])
            ):
                raise QualificationPreparationError(
                    f"{repo}#{number}: invalid cached repository-transfer provenance"
                )
            _validate_pr_url(pull["url"], canonical_repo, number)
        else:
            raise QualificationPreparationError(
                f"{repo}#{number}: unsupported cached source method"
            )
        return merge_commit

    @staticmethod
    def _missing_pull(response: Mapping[str, Any], alias: str) -> bool:
        errors = response.get("errors", [])
        return any(
            isinstance(error, dict)
            and error.get("type") == "NOT_FOUND"
            and error.get("path") == [alias, "pullRequest"]
            for error in errors
        )

    @staticmethod
    def _missing_repository(response: Mapping[str, Any], alias: str) -> bool:
        errors = response.get("errors", [])
        return any(
            isinstance(error, dict)
            and error.get("type") == "NOT_FOUND"
            and error.get("path") == [alias]
            for error in errors
        )

    def _repository_transfer_fallback(
        self,
        candidate: Mapping[str, Any],
        record: Mapping[str, Any],
    ) -> str:
        """Recover a transferred repository only from exact authenticated evidence."""

        requested_repo = candidate["repo"]
        number = candidate["source_pr_number"]
        base_commit = record["base_commit"]
        search_raw = self._request(
            [
                "-X",
                "GET",
                "search/commits",
                "-H",
                "Accept: application/vnd.github+json",
                "-f",
                f"q={base_commit}",
                "-f",
                "per_page=100",
            ]
        )
        try:
            search = json.loads(search_raw)
            items = search["items"]
            complete = search["incomplete_results"] is False
            total = search["total_count"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: malformed repository-transfer search"
            ) from exc
        if (
            not complete
            or not isinstance(items, list)
            or total != len(items)
            or total > 100
        ):
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: repository-transfer search is incomplete"
            )

        discovery_results: list[dict[str, str]] = []
        for item in items:
            try:
                sha = item["sha"]
                full_name = item["repository"]["full_name"]
            except (KeyError, TypeError) as exc:
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: malformed repository-transfer result"
                ) from exc
            if (
                sha != base_commit
                or not isinstance(full_name, str)
                or full_name.count("/") != 1
            ):
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: repository-transfer result disagrees"
                )
            discovery_results.append({"repository": full_name, "sha": sha})
        discovery_results.sort(key=lambda item: item["repository"].casefold())
        basename = requested_repo.rsplit("/", 1)[-1].casefold()
        possible_repositories = sorted(
            {
                item["repository"]
                for item in discovery_results
                if item["repository"].rsplit("/", 1)[-1].casefold() == basename
            },
            key=str.casefold,
        )
        if not possible_repositories:
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: no same-name repository contains the frozen base"
            )

        fields = []
        for index, repository in enumerate(possible_repositories):
            owner, name = repository.split("/", 1)
            fields.append(
                f"c{index}:repository(owner:{json.dumps(owner)},name:{json.dumps(name)})"
                "{nameWithOwner pullRequest(number:"
                f"{number}"
                "){number url merged baseRefOid headRefOid mergeCommit{oid}}}"
            )
        query = "query{" + "".join(fields) + "}"
        metadata_raw = self._request(["graphql", "-f", f"query={query}"])
        try:
            metadata_response = json.loads(metadata_raw)
            metadata_data = metadata_response["data"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: malformed transfer PR metadata"
            ) from exc

        matches: dict[str, dict[str, Any]] = {}
        for index, discovered_repo in enumerate(possible_repositories):
            alias = f"c{index}"
            repository = metadata_data.get(alias)
            if repository is None:
                if self._missing_repository(metadata_response, alias):
                    continue
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: transfer candidate repository lookup failed"
                )
            try:
                canonical_repo = repository["nameWithOwner"]
                pull = repository["pullRequest"]
            except (KeyError, TypeError) as exc:
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: malformed transfer candidate metadata"
                ) from exc
            if (
                not isinstance(canonical_repo, str)
                or canonical_repo.count("/") != 1
                or canonical_repo.rsplit("/", 1)[-1].casefold() != basename
            ):
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: transfer candidate repository disagrees"
                )
            if pull is None:
                if self._missing_pull(metadata_response, alias):
                    continue
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: transfer candidate PR lookup failed"
                )
            try:
                merge_commit = pull["mergeCommit"]["oid"]
                pr_record = {
                    "number": pull["number"],
                    "url": pull["url"],
                    "merged": pull["merged"],
                    "base_commit": pull["baseRefOid"],
                    "head_commit": pull["headRefOid"],
                    "merge_commit": merge_commit,
                }
            except (KeyError, TypeError) as exc:
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: malformed transfer candidate PR"
                ) from exc
            _validate_pr_url(pr_record["url"], canonical_repo, number)
            if (
                pr_record["number"] != number
                or pr_record["merged"] is not True
                or pr_record["base_commit"] != base_commit
                or not isinstance(pr_record["head_commit"], str)
                or not GIT_SHA_RE.fullmatch(pr_record["head_commit"])
                or not isinstance(merge_commit, str)
                or not GIT_SHA_RE.fullmatch(merge_commit)
            ):
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: transfer candidate PR provenance disagrees"
                )
            if canonical_repo.casefold() in matches:
                raise QualificationPreparationError(
                    f"{requested_repo}#{number}: transfer candidate is ambiguous"
                )
            matches[canonical_repo.casefold()] = {
                "canonical_repo": canonical_repo,
                "pull": pr_record,
            }

        if len(matches) != 1:
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: repository-transfer match is missing or ambiguous"
            )
        selected = next(iter(matches.values()))
        canonical_repo = selected["canonical_repo"]
        pr_record = selected["pull"]
        _validate_source_pr_url(
            candidate["source_pr_url"], requested_repo, canonical_repo, number
        )
        commit_raw = self._request(
            [f"repos/{canonical_repo}/commits/{pr_record['merge_commit']}"]
        )
        try:
            commit_response = json.loads(commit_raw)
            commit_record = {
                "sha": commit_response["sha"],
                "tree": commit_response["commit"]["tree"]["sha"],
                "parents": [parent["sha"] for parent in commit_response["parents"]],
            }
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: malformed transferred merge commit"
            ) from exc
        if (
            commit_record["sha"] != pr_record["merge_commit"]
            or not GIT_SHA_RE.fullmatch(commit_record["tree"])
            or not commit_record["parents"]
            or not all(
                isinstance(parent, str) and GIT_SHA_RE.fullmatch(parent)
                for parent in commit_record["parents"]
            )
        ):
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: transferred merge commit disagrees"
            )
        authoritative_diff = self._request(
            [
                "-X",
                "GET",
                f"repos/{canonical_repo}/pulls/{number}",
                "-H",
                "Accept: application/vnd.github.v3.diff",
            ]
        )
        expected_sections = _expected_patch_sections(record)
        if _canonical_patch_sections(authoritative_diff) != expected_sections:
            raise QualificationPreparationError(
                f"{requested_repo}#{number}: transferred PR diff does not match frozen product/test patches"
            )
        canonical_patch_sha = _patch_sections_sha256(expected_sections)
        self._store_source_cache(
            requested_repo,
            number,
            {
                "schema_version": SOURCE_CACHE_SCHEMA,
                "requested_repo": requested_repo,
                "canonical_repo": canonical_repo,
                "pr_number": number,
                "source_pr_url": candidate["source_pr_url"],
                "method": "repository_transfer_fallback",
                "merge_commit_sha": pr_record["merge_commit"],
                "record_bindings": self._record_bindings(record),
                "evidence": {
                    "discovery_query": base_commit,
                    "discovery_results": discovery_results,
                    "discovery_complete": complete,
                    "discovery_total": total,
                    "pull_request": pr_record,
                    "merge_commit": commit_record,
                    "canonical_patch_sections_sha256": canonical_patch_sha,
                    "authoritative_diff_sha256": _sha256_bytes(
                        authoritative_diff.encode()
                    ),
                },
            },
        )
        return pr_record["merge_commit"]

    def _history_fallback(
        self,
        candidate: Mapping[str, Any],
        record: Mapping[str, Any],
        canonical_repo: str,
    ) -> str:
        repo = candidate["repo"]
        number = candidate["source_pr_number"]
        query = f'repo:{canonical_repo} "Merge pull request #{number} from"'
        raw = self._request(
            [
                "-X",
                "GET",
                "search/commits",
                "-H",
                "Accept: application/vnd.github+json",
                "-f",
                f"q={query}",
                "-f",
                "per_page=100",
            ]
        )
        try:
            search = json.loads(raw)
            items = search["items"]
            complete = search["incomplete_results"] is False
            total = search["total_count"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                f"{repo}#{number}: malformed commit-search response"
            ) from exc
        exact = []
        for item in items if isinstance(items, list) else ():
            message = (
                item.get("commit", {}).get("message")
                if isinstance(item, dict)
                else None
            )
            if isinstance(message, str) and re.fullmatch(
                rf"Merge pull request #{number} from [^\r\n]+", message.splitlines()[0]
            ):
                exact.append(item)
        if not complete or total != len(items) or len(exact) != 1:
            raise QualificationPreparationError(
                f"{repo}#{number}: merge-history fallback is missing or ambiguous"
            )
        merge_commit = exact[0].get("sha")
        if not isinstance(merge_commit, str) or not GIT_SHA_RE.fullmatch(merge_commit):
            raise QualificationPreparationError(
                f"{repo}#{number}: fallback search returned an invalid commit"
            )

        detail_raw = self._request([f"repos/{canonical_repo}/commits/{merge_commit}"])
        try:
            detail = json.loads(detail_raw)
            message = detail["commit"]["message"]
            parents = [parent["sha"] for parent in detail["parents"]]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                f"{repo}#{number}: malformed merge-commit response"
            ) from exc
        if (
            detail.get("sha") != merge_commit
            or message != exact[0]["commit"]["message"]
            or len(parents) != 2
            or not all(GIT_SHA_RE.fullmatch(parent) for parent in parents)
        ):
            raise QualificationPreparationError(
                f"{repo}#{number}: fallback commit is not the exact two-parent merge"
            )
        branch_head = parents[1]
        base_commit = record["base_commit"]
        compare_endpoint = (
            f"repos/{canonical_repo}/compare/{base_commit}...{branch_head}"
        )
        compare_raw = self._request(["-X", "GET", compare_endpoint])
        try:
            compare = json.loads(compare_raw)
            commits = compare["commits"]
            ancestry_ok = (
                compare["status"] == "ahead"
                and compare["base_commit"]["sha"] == base_commit
                and compare["merge_base_commit"]["sha"] == base_commit
                and isinstance(commits, list)
                and commits
                and compare["total_commits"] == len(commits)
                and commits[-1]["sha"] == branch_head
            )
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                f"{repo}#{number}: malformed ancestry comparison"
            ) from exc
        if not ancestry_ok:
            raise QualificationPreparationError(
                f"{repo}#{number}: frozen base is not the fallback branch-head ancestor"
            )
        authoritative_diff = self._request(
            [
                "-X",
                "GET",
                compare_endpoint,
                "-H",
                "Accept: application/vnd.github.v3.diff",
            ]
        )
        expected_sections = _expected_patch_sections(record)
        actual_sections = _canonical_patch_sections(authoritative_diff)
        if actual_sections != expected_sections:
            raise QualificationPreparationError(
                f"{repo}#{number}: authoritative fallback diff does not match frozen product/test patches"
            )
        canonical_patch_sha = _patch_sections_sha256(expected_sections)
        evidence = {
            "merge_message": message,
            "parents": parents,
            "branch_head": branch_head,
            "compare_status": compare["status"],
            "canonical_patch_sections_sha256": canonical_patch_sha,
            "authoritative_diff_sha256": _sha256_bytes(authoritative_diff.encode()),
        }
        self._store_source_cache(
            repo,
            number,
            {
                "schema_version": SOURCE_CACHE_SCHEMA,
                "requested_repo": repo,
                "canonical_repo": canonical_repo,
                "pr_number": number,
                "source_pr_url": candidate["source_pr_url"],
                "method": "merge_history_fallback",
                "merge_commit_sha": merge_commit,
                "record_bindings": self._record_bindings(record),
                "evidence": evidence,
            },
        )
        return merge_commit

    def merge_commits(
        self,
        candidates: Sequence[Mapping[str, Any]],
        records: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        missing: list[Mapping[str, Any]] = []
        for candidate in candidates:
            instance_id = candidate["instance_id"]
            cached = self._cached_source(candidate, records[instance_id])
            if cached is None:
                missing.append(candidate)
            else:
                result[instance_id] = cached

        for offset in range(0, len(missing), self.batch_size):
            batch = missing[offset : offset + self.batch_size]
            fields = []
            for index, candidate in enumerate(batch):
                owner, name = candidate["repo"].split("/", 1)
                fields.append(
                    f"r{index}:repository(owner:{json.dumps(owner)},name:{json.dumps(name)})"
                    "{nameWithOwner pullRequest(number:"
                    f"{candidate['source_pr_number']}"
                    "){number url merged mergeCommit{oid}}}"
                )
            query = "query{" + "".join(fields) + "}"
            raw = self._request(["graphql", "-f", f"query={query}"])
            try:
                response = json.loads(raw)
                data = response["data"]
            except (KeyError, TypeError, json.JSONDecodeError) as exc:
                raise QualificationPreparationError(
                    "GitHub GraphQL response is malformed"
                ) from exc
            errors: list[str] = []
            fallbacks: list[tuple[Mapping[str, Any], str]] = []
            repository_transfers: list[Mapping[str, Any]] = []
            for index, candidate in enumerate(batch):
                repo = candidate["repo"]
                number = candidate["source_pr_number"]
                try:
                    repository = data[f"r{index}"]
                    if repository is None:
                        if self._missing_repository(response, f"r{index}"):
                            repository_transfers.append(candidate)
                            continue
                        raise QualificationPreparationError(
                            "GitHub returned no repository without an exact NOT_FOUND error"
                        )
                    canonical_repo = repository["nameWithOwner"]
                    if (
                        not isinstance(canonical_repo, str)
                        or canonical_repo.count("/") != 1
                    ):
                        raise QualificationPreparationError(
                            "GitHub returned an invalid canonical repository"
                        )
                    _validate_source_pr_url(
                        candidate["source_pr_url"], repo, canonical_repo, number
                    )
                    pull = repository["pullRequest"]
                    if pull is None:
                        if self._missing_pull(response, f"r{index}"):
                            fallbacks.append((candidate, canonical_repo))
                            continue
                        raise QualificationPreparationError(
                            "GitHub returned no PR without an exact NOT_FOUND error"
                        )
                    _validate_pr_url(pull["url"], canonical_repo, number)
                    merge_commit = pull["mergeCommit"]["oid"]
                    if pull["number"] != number or pull["merged"] is not True:
                        raise QualificationPreparationError("PR is not merged")
                    if not isinstance(merge_commit, str) or not GIT_SHA_RE.fullmatch(
                        merge_commit
                    ):
                        raise QualificationPreparationError(
                            "merge commit is not a full Git SHA"
                        )
                except (KeyError, TypeError, QualificationPreparationError) as exc:
                    errors.append(f"{repo}#{number}: {exc}")
                    continue
                cached = {
                    "schema_version": SOURCE_CACHE_SCHEMA,
                    "requested_repo": repo,
                    "canonical_repo": canonical_repo,
                    "pr_number": number,
                    "source_pr_url": candidate["source_pr_url"],
                    "method": "pull_api",
                    "merge_commit_sha": merge_commit,
                    "record_bindings": self._record_bindings(
                        records[candidate["instance_id"]]
                    ),
                    "evidence": {"url": pull["url"], "merged": True},
                }
                self._store_source_cache(repo, number, cached)
                result[candidate["instance_id"]] = merge_commit
            if errors:
                raise QualificationPreparationError(
                    "authoritative PR metadata could not be resolved: "
                    + "; ".join(errors[:5])
                )
            for candidate, canonical_repo in fallbacks:
                result[candidate["instance_id"]] = self._history_fallback(
                    candidate,
                    records[candidate["instance_id"]],
                    canonical_repo,
                )
            for candidate in repository_transfers:
                result[candidate["instance_id"]] = self._repository_transfer_fallback(
                    candidate,
                    records[candidate["instance_id"]],
                )
        return result


class ImageResolver:
    """Resolve registry metadata one image at a time without pulling layers."""

    def __init__(
        self,
        cache_dir: Path,
        *,
        docker: str = "docker",
        max_new_resolutions: int = 456,
        runner: Callable[[Sequence[str]], str] = _run_command,
    ) -> None:
        if max_new_resolutions < 0:
            raise QualificationPreparationError(
                "image resolution budget cannot be negative"
            )
        self.cache_dir = cache_dir
        self.docker = docker
        self.max_new_resolutions = max_new_resolutions
        self.runner = runner
        self.new_resolutions = 0

    def _cache_path(self, image_name: str) -> Path:
        key = hashlib.sha256(image_name.encode()).hexdigest()
        return self.cache_dir / "images" / f"{key}.json"

    @staticmethod
    def _validate(value: Mapping[str, Any], image_name: str) -> Mapping[str, Any]:
        if set(value) != {"image_name", "digest", "workdir", "platform"}:
            raise QualificationPreparationError(
                f"{image_name}: malformed image cache entry"
            )
        if value["image_name"] != image_name or value["platform"] != "linux/amd64":
            raise QualificationPreparationError(
                f"{image_name}: image cache binding disagrees"
            )
        if not isinstance(value["digest"], str) or not IMAGE_DIGEST_RE.fullmatch(
            value["digest"]
        ):
            raise QualificationPreparationError(f"{image_name}: invalid image digest")
        workdir = value["workdir"]
        pure = (
            PurePosixPath(workdir) if isinstance(workdir, str) else PurePosixPath(".")
        )
        if (
            not isinstance(workdir, str)
            or not workdir.startswith("/")
            or workdir == "/"
            or ".." in pure.parts
        ):
            raise QualificationPreparationError(
                f"{image_name}: unsafe or missing image workdir"
            )
        return value

    def resolve(self, image_name: str) -> Mapping[str, Any]:
        cached = _read_cached_json(self._cache_path(image_name))
        if cached is not None:
            return self._validate(cached, image_name)
        if self.new_resolutions >= self.max_new_resolutions:
            raise QualificationPreparationError(
                "image metadata budget exhausted; rerun with the same cache to resume"
            )
        self.new_resolutions += 1
        raw = self.runner(
            [
                self.docker,
                "buildx",
                "imagetools",
                "inspect",
                image_name,
                "--format",
                "{{json .}}",
            ]
        )
        try:
            metadata = json.loads(raw)
            manifest = metadata["manifest"]
            image = metadata["image"]
            manifests = manifest.get("manifests")
            if manifests is None:
                digest = manifest["digest"]
                platform_image = image
            else:
                matches = [
                    item
                    for item in manifests
                    if item.get("platform", {}).get("os") == "linux"
                    and item.get("platform", {}).get("architecture") == "amd64"
                    and item.get("platform", {}).get("variant") in (None, "")
                ]
                if len(matches) != 1:
                    raise QualificationPreparationError(
                        "registry has ambiguous linux/amd64 manifests"
                    )
                digest = matches[0]["digest"]
                platform_image = image["linux/amd64"]
            if (
                platform_image.get("os") != "linux"
                or platform_image.get("architecture") != "amd64"
            ):
                raise QualificationPreparationError(
                    "registry platform metadata disagrees"
                )
            workdir = platform_image["config"]["WorkingDir"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise QualificationPreparationError(
                f"{image_name}: malformed registry metadata"
            ) from exc
        value = self._validate(
            {
                "image_name": image_name,
                "digest": digest,
                "workdir": workdir,
                "platform": "linux/amd64",
            },
            image_name,
        )
        _atomic_write(self._cache_path(image_name), _canonical_bytes(value))
        return value


@dataclass(frozen=True)
class PatchHunk:
    old_path: str
    new_path: str
    before: str
    after: str
    before_changed_rows: tuple[int, ...]
    after_changed_rows: tuple[int, ...]


def parse_patch_hunks(patch: str) -> list[PatchHunk]:
    """Reconstruct before/after source fragments from every unified-diff hunk."""

    result: list[PatchHunk] = []
    paths: tuple[str, str] | None = None
    before: list[str] = []
    after: list[str] = []
    before_rows: list[int] = []
    after_rows: list[int] = []
    old_remaining = new_remaining = 0
    in_hunk = False

    def finish_hunk() -> None:
        nonlocal before, after, before_rows, after_rows, in_hunk
        if not in_hunk:
            return
        if old_remaining or new_remaining:
            raise QualificationPreparationError("gold patch contains a truncated hunk")
        assert paths is not None
        if not before_rows and not after_rows:
            raise QualificationPreparationError(
                "gold patch contains a hunk with no edit"
            )
        result.append(
            PatchHunk(
                old_path=paths[0],
                new_path=paths[1],
                before="\n".join(before) + ("\n" if before else ""),
                after="\n".join(after) + ("\n" if after else ""),
                before_changed_rows=tuple(before_rows),
                after_changed_rows=tuple(after_rows),
            )
        )
        before, after, before_rows, after_rows = [], [], [], []
        in_hunk = False

    for line in patch.splitlines():
        if in_hunk:
            if line == r"\ No newline at end of file":
                continue
            prefix = line[:1]
            if prefix not in {" ", "+", "-"}:
                raise QualificationPreparationError(
                    "gold patch contains malformed hunk payload"
                )
            content = line[1:]
            if prefix in {" ", "-"}:
                if old_remaining <= 0:
                    raise QualificationPreparationError(
                        "gold patch exceeds declared old hunk size"
                    )
                if prefix == "-":
                    before_rows.append(len(before))
                before.append(content)
                old_remaining -= 1
            if prefix in {" ", "+"}:
                if new_remaining <= 0:
                    raise QualificationPreparationError(
                        "gold patch exceeds declared new hunk size"
                    )
                if prefix == "+":
                    after_rows.append(len(after))
                after.append(content)
                new_remaining -= 1
            if old_remaining == 0 and new_remaining == 0:
                finish_hunk()
            continue
        if line.startswith("diff --git "):
            paths = _diff_header_paths(line)
            continue
        match = HUNK_HEADER_RE.fullmatch(line)
        if match:
            if paths is None:
                raise QualificationPreparationError(
                    "gold patch hunk precedes its file header"
                )
            old_remaining = int(match.group("old_count") or 1)
            new_remaining = int(match.group("new_count") or 1)
            in_hunk = True
            before, after, before_rows, after_rows = [], [], [], []
    finish_hunk()
    if not result:
        raise QualificationPreparationError("gold patch contains no source hunks")
    return result


class AstFingerprinter:
    """Derive content-bound tree-sitter edit fingerprints from patch source."""

    def __init__(self, parser_factory: Callable[[str], Any] | None = None) -> None:
        if parser_factory is None:
            try:
                from tree_sitter_language_pack import get_parser
            except ImportError as exc:
                raise QualificationPreparationError(
                    "tree-sitter-language-pack==1.22.1 is required; install requirements-qualification.txt"
                ) from exc
            parser_factory = get_parser
        self.parser_factory = parser_factory
        self.parsers: dict[str, Any] = {}

    def _parser(self, language: str) -> Any:
        grammar = LANGUAGE_GRAMMARS.get(language)
        if grammar is None:
            raise QualificationPreparationError(
                f"unsupported AST language {language!r}"
            )
        if grammar not in self.parsers:
            try:
                self.parsers[grammar] = self.parser_factory(grammar)
            except Exception as exc:
                raise QualificationPreparationError(
                    f"could not load pinned AST grammar {grammar}: {exc}"
                ) from exc
        return self.parsers[grammar]

    @staticmethod
    def _select_node(tree: Any, source: bytes, rows: tuple[int, ...]) -> Any:
        root = tree.root_node
        if not rows:
            return root
        lines = source.splitlines()
        first, last = min(rows), max(rows)
        end_column = len(lines[last]) if last < len(lines) else 0
        try:
            node = root.named_descendant_for_point_range((first, 0), (last, end_column))
        except (AttributeError, TypeError):
            node = root
        while getattr(node, "parent", None) is not None and not getattr(
            node, "named_children", ()
        ):
            node = node.parent
        return node

    @staticmethod
    def _tree_shape(node: Any, source: bytes) -> Mapping[str, Any]:
        children = list(getattr(node, "named_children", ()))
        payload: dict[str, Any] = {
            "type": node.type,
            "source_sha256": _sha256_bytes(source[node.start_byte : node.end_byte]),
        }
        if children:
            payload["children"] = [
                AstFingerprinter._tree_shape(child, source) for child in children
            ]
        return payload

    @staticmethod
    def _symbol(node: Any, source: bytes) -> str:
        candidate = None
        try:
            candidate = node.child_by_field_name("name")
        except AttributeError:
            pass
        queue = [node]
        while candidate is None and queue:
            current = queue.pop(0)
            if current.type in {"identifier", "type_identifier", "property_identifier"}:
                candidate = current
                break
            queue.extend(list(getattr(current, "named_children", ())))
            if len(queue) > 2000:
                break
        if candidate is None:
            return ""
        raw = source[candidate.start_byte : candidate.end_byte].decode(
            "utf-8", errors="replace"
        )
        return " ".join(raw.split())[:160]

    def _node(
        self, source_text: str, rows: tuple[int, ...], language: str
    ) -> tuple[Any, bytes, str]:
        source = source_text.encode()
        tree = self._parser(language).parse(source)
        node = self._select_node(tree, source, rows)
        digest = _sha256_bytes(_canonical_bytes(self._tree_shape(node, source)))
        return node, source, digest

    def edits(self, patch: str, language: str) -> list[Mapping[str, Any]]:
        edits: list[Mapping[str, Any]] = []
        for hunk in parse_patch_hunks(patch):
            has_before = bool(hunk.before_changed_rows)
            has_after = bool(hunk.after_changed_rows)
            renamed = hunk.old_path != hunk.new_path
            before_rows = hunk.before_changed_rows
            after_rows = hunk.after_changed_rows
            if renamed and hunk.before and not before_rows:
                before_rows = tuple(range(len(hunk.before.splitlines())))
            if renamed and hunk.after and not after_rows:
                after_rows = tuple(range(len(hunk.after.splitlines())))
            before_data = (
                self._node(hunk.before, before_rows, language)
                if has_before or renamed
                else None
            )
            after_data = (
                self._node(hunk.after, after_rows, language)
                if has_after or renamed
                else None
            )

            if renamed:
                if before_data is not None:
                    node, source, digest = before_data
                    edits.append(
                        {
                            "path": hunk.old_path,
                            "operation": "delete",
                            "node_type": node.type,
                            "symbol": self._symbol(node, source),
                            "before_sha256": digest,
                            "after_sha256": None,
                        }
                    )
                if after_data is not None:
                    node, source, digest = after_data
                    edits.append(
                        {
                            "path": hunk.new_path,
                            "operation": "add",
                            "node_type": node.type,
                            "symbol": self._symbol(node, source),
                            "before_sha256": None,
                            "after_sha256": digest,
                        }
                    )
                continue

            if before_data is None:
                operation = "add"
                node, source, after_digest = after_data  # type: ignore[misc]
                before_digest = None
            elif after_data is None:
                operation = "delete"
                node, source, before_digest = before_data
                after_digest = None
            else:
                operation = "update"
                before_node, _, before_digest = before_data
                node, source, after_digest = after_data
                if before_node.type != node.type:
                    node_type = f"{before_node.type}->{node.type}"
                else:
                    node_type = node.type
            edits.append(
                {
                    "path": hunk.new_path,
                    "operation": operation,
                    "node_type": node_type if operation == "update" else node.type,
                    "symbol": self._symbol(node, source),
                    "before_sha256": before_digest,
                    "after_sha256": after_digest,
                }
            )
        unique = {
            json.dumps(edit, sort_keys=True, separators=(",", ":")): edit
            for edit in edits
        }
        ordered = [unique[key] for key in sorted(unique)]
        expected_paths = patch_paths(patch)
        actual_paths = {edit["path"] for edit in ordered}
        if actual_paths != expected_paths:
            raise QualificationPreparationError(
                f"AST edit paths disagree with patch (missing={sorted(expected_paths - actual_paths)}, "
                f"extra={sorted(actual_paths - expected_paths)})"
            )
        return ordered


def _source_binding() -> Mapping[str, Any]:
    return {
        "dataset": DATASET,
        "revision": DATASET_REVISION,
        "split": "train",
        "file": DATASET_FILE,
        "sha256": SOURCE_SHA256,
        "rows": SOURCE_ROWS,
    }


def _tar_bytes(
    manifest: Mapping[str, Any], parser_source: bytes, parser_names: Sequence[str]
) -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        members = [("materials.json", _canonical_bytes(manifest))]
        members.extend(
            (f"parsers/{name}.py", parser_source) for name in sorted(parser_names)
        )
        for name, payload in members:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o444
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            archive.addfile(info, io.BytesIO(payload))
    return output.getvalue()


def _resolve_path(repo_root: Path, path: Path) -> Path:
    return (repo_root / path).resolve() if not path.is_absolute() else path.resolve()


def prepare(
    *,
    repo_root: Path,
    plan_path: Path,
    dataset_path: Path,
    cache_dir: Path,
    material_package_path: Path,
    image_lock_path: Path,
    github: GitHubResolver,
    images: ImageResolver,
    ast: AstFingerprinter,
) -> Mapping[str, Any]:
    code_root = Path(__file__).resolve().parents[1]
    if repo_root.resolve() != code_root:
        raise QualificationPreparationError(
            f"repo_root must be the checkout containing this command: {code_root}"
        )
    _reject_holdout_paths(
        repo_root,
        (plan_path, dataset_path, cache_dir, material_package_path, image_lock_path),
    )
    if cache_dir.exists() and (not cache_dir.is_dir() or cache_dir.is_symlink()):
        raise QualificationPreparationError(
            "cache directory must be a real directory, not a symlink"
        )
    cache_dir.mkdir(parents=True, exist_ok=True)
    for path in (plan_path, dataset_path):
        if not path.is_file() or path.is_symlink():
            raise QualificationPreparationError(
                f"input must be a regular non-symlink file: {path}"
            )
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QualificationPreparationError(f"cannot read frozen plan: {exc}") from exc
    validate_sequential_plan(plan)
    if canonical_plan_sha256(plan) != FROZEN_PLAN_CANONICAL_SHA256:
        raise QualificationPreparationError(
            "plan canonical SHA-256 is not the frozen authority"
        )
    if _sha256_file(plan_path) != FROZEN_PLAN_FILE_SHA256:
        raise QualificationPreparationError(
            "plan file SHA-256 is not the frozen authority"
        )

    dataset_records = _load_selected_dataset_records(dataset_path, plan)
    candidates = [candidate for _, candidate in _candidate_sequence(plan)]
    parser_source = github.parser_source()
    parser_sha = _sha256_bytes(parser_source)
    used_parsers = sorted({candidate["log_parser"] for candidate in candidates})
    if not set(used_parsers) <= SUPPORTED_LOG_PARSERS:
        raise QualificationPreparationError(
            "frozen plan asks for an unsupported log parser"
        )
    for parser_name in used_parsers:
        load_pinned_parser_bytes(parser_source, parser_name, parser_sha)
    merge_commits = github.merge_commits(candidates, dataset_records)

    material_tasks = []
    image_entries = []
    for candidate in candidates:
        instance_id = candidate["instance_id"]
        record = dataset_records[instance_id]
        material_tasks.append(
            {
                "instance_id": instance_id,
                "problem_statement": record["problem_statement"],
                "gold_patch": record["patch"],
                "test_patch": record["test_patch"],
                "fail_to_pass": record["FAIL_TO_PASS"],
                "pass_to_pass": record["PASS_TO_PASS"],
                "install_config": record["install_config"],
                "source_identity": {
                    "merge_commit": merge_commits[instance_id],
                    "episode_ids": [],
                },
                "ast_edits": ast.edits(record["patch"], candidate["language"]),
            }
        )
        image = images.resolve(candidate["image_name"])
        image_entries.append(
            {
                "instance_id": instance_id,
                "image_name": candidate["image_name"],
                "reference": f"{_image_repository(candidate['image_name'])}@{image['digest']}",
                "digest": image["digest"],
                "workdir": image["workdir"],
            }
        )

    plan_sha = canonical_plan_sha256(plan)
    manifest = {
        "schema_version": MATERIAL_SCHEMA,
        "source": _source_binding(),
        "candidate_plan_sha256": plan_sha,
        "ast_fingerprint_spec": AST_SPEC,
        "parser_files": {
            name: {"path": f"parsers/{name}.py", "sha256": parser_sha}
            for name in used_parsers
        },
        "tasks": material_tasks,
    }
    image_lock = {
        "schema_version": IMAGE_LOCK_SCHEMA,
        "source": _source_binding(),
        "candidate_plan_sha256": plan_sha,
        "platform": "linux/amd64",
        "entries": image_entries,
    }
    material_payload = _tar_bytes(manifest, parser_source, used_parsers)
    image_payload = _canonical_bytes(image_lock)

    material_package_path.parent.mkdir(parents=True, exist_ok=True)
    image_lock_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{material_package_path.name}.",
        dir=material_package_path.parent,
        delete=False,
    ) as handle:
        material_temp = Path(handle.name)
        handle.write(material_payload)
    with tempfile.NamedTemporaryFile(
        prefix=f".{image_lock_path.name}.", dir=image_lock_path.parent, delete=False
    ) as handle:
        image_temp = Path(handle.name)
        handle.write(image_payload)
    try:
        _read_material_package(material_temp, plan, dataset_records)
        _read_image_lock(image_temp, plan)
        for destination, temporary in (
            (material_package_path, material_temp),
            (image_lock_path, image_temp),
        ):
            if destination.exists():
                if not destination.is_file() or destination.is_symlink():
                    raise QualificationPreparationError(
                        f"output is not a regular file: {destination}"
                    )
                if _sha256_file(destination) != _sha256_file(temporary):
                    raise QualificationPreparationError(
                        f"refusing to replace different sealed output: {destination}"
                    )
                temporary.unlink()
            else:
                os.replace(temporary, destination)
    finally:
        material_temp.unlink(missing_ok=True)
        image_temp.unlink(missing_ok=True)

    return {
        "schema_version": "mini-gibson-qualification-preparation-report/v1",
        "candidate_count": len(candidates),
        "candidate_plan_sha256": plan_sha,
        "dataset_sha256": SOURCE_SHA256,
        "material_package": {
            "path": str(material_package_path),
            "sha256": _sha256_file(material_package_path),
        },
        "image_lock": {
            "path": str(image_lock_path),
            "sha256": _sha256_file(image_lock_path),
        },
        "parser_source": {
            "repository": PARSER_REPOSITORY,
            "revision": PARSER_REVISION,
            "path": PARSER_PATH,
            "git_blob_sha1": PARSER_BLOB_SHA1,
            "sha256": parser_sha,
        },
        "new_github_requests": github.new_requests,
        "new_image_resolutions": images.new_resolutions,
        "docker_pulls": 0,
        "formal_model_outcomes_observed": False,
        "final_holdout_status": "sealed_not_read_or_run",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    freeze = Path("evaluation/frozen/mini-gibson-v2-sequential-2026-10-17")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--plan", type=Path, default=freeze / "sequential-plan.json")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--material-package", type=Path, required=True)
    parser.add_argument("--image-lock", type=Path, required=True)
    parser.add_argument("--gh", default="gh")
    parser.add_argument("--docker", default="docker")
    parser.add_argument("--max-new-github-requests", type=int, default=25)
    parser.add_argument("--github-batch-size", type=int, default=25)
    parser.add_argument("--max-new-image-resolutions", type=int, default=456)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    cache_dir = _resolve_path(repo_root, args.cache_dir)
    github = GitHubResolver(
        cache_dir,
        gh=args.gh,
        max_new_requests=args.max_new_github_requests,
        batch_size=args.github_batch_size,
    )
    images = ImageResolver(
        cache_dir,
        docker=args.docker,
        max_new_resolutions=args.max_new_image_resolutions,
    )
    report = prepare(
        repo_root=repo_root,
        plan_path=_resolve_path(repo_root, args.plan),
        dataset_path=args.dataset.resolve(),
        cache_dir=cache_dir,
        material_package_path=_resolve_path(repo_root, args.material_package),
        image_lock_path=_resolve_path(repo_root, args.image_lock),
        github=github,
        images=images,
        ast=AstFingerprinter(),
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
