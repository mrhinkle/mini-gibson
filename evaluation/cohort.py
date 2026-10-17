"""Fail-closed validation for frozen real-repository cohort locks.

The lock is internal provenance. Only :func:`agent_projection` may create input
for the model-facing runner; hidden verifier and source identities are never
copied into that projection.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


LOCK_SCHEMA = "mini-gibson-real-repo-cohort/v1"
REGISTRY_SCHEMA = "mini-gibson-exclusion-registry/v1"
DATASET = "nebius/SWE-rebench-V2"
DATASET_REVISION = "10483de0f50fe5da545942705a76c6150171af7f"
SELECTION_POLICY = "swe-rebench-v2-balanced/v1"
PARSER_SOURCE_REVISION = "c71902a8cf8d2b725f63d51f199f4d3e56f68d2d"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
INSTANCE_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
IMAGE_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
COMMIT_IN_TEXT_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", re.I)

TOP_KEYS = {
    "schema_version",
    "cohort_id",
    "mode",
    "source",
    "selection",
    "exclusion_registry",
    "sealed_verifier_package",
    "parser",
    "tasks",
}
SOURCE_KEYS = {"dataset", "revision", "split", "dataset_card_url"}
SELECTION_KEYS = {
    "policy_version",
    "seed",
    "expected_tasks",
    "min_languages",
    "min_repositories",
    "max_tasks_per_repo",
}
REGISTRY_REF_KEYS = {"path", "sha256"}
PARSER_KEYS = {"source_repo", "source_revision", "vendored_parser_sha256"}
TASK_KEYS = {
    "selection_rank",
    "instance_id",
    "repo",
    "source_identity",
    "base_commit",
    "problem_statement",
    "language",
    "license",
    "split",
    "image",
    "install_config_sha256",
    "task_projection_sha256",
    "fingerprints",
    "qualification",
    "log_parser",
    "verify_timeout_s",
}
SOURCE_IDENTITY_KEYS = {
    "pr_url",
    "pr_number",
    "issue_urls",
    "merge_commit",
    "episode_ids",
}
IMAGE_KEYS = {"reference", "digest", "platform", "workdir"}
FINGERPRINT_KEYS = {
    "issue_text_sha256",
    "patch_sha256",
    "test_patch_sha256",
    "changed_files_sha256",
    "ast_edits_sha256",
    "image_cluster_sha256",
}
QUALIFICATION_KEYS = {
    "status",
    "receipt_sha256",
    "base_fail_repeats",
    "gold_pass_repeats",
}
REGISTRY_KEYS = {"schema_version", "registry_id", "source_digests", "entries"}
REGISTRY_SOURCE_KEYS = {"name", "sha256"}
REGISTRY_ENTRY_KEYS = {"kind", "value", "source"}

HIDDEN_FIELD_NAMES = {
    "patch",
    "gold_patch",
    "test_patch",
    "fail_to_pass",
    "pass_to_pass",
    "pr_description",
    "llm_metadata",
    "hints",
    "qualification_logs",
}

SUPPORTED_REGISTRY_KINDS = {
    "instance_id",
    "repo",
    "repo_pr",
    "repo_issue",
    "base_commit",
    "merge_commit",
    "image_cluster_sha256",
    "patch_sha256",
    "test_patch_sha256",
    "issue_text_sha256",
    "changed_files_sha256",
    "ast_edits_sha256",
    "episode_id",
    "statement_token",
}

SUPPORTED_LOG_PARSERS = {
    "parse_java_mvn",
    "parse_log_cargo",
    "parse_log_dart_v3",
    "parse_log_elixir",
    "parse_log_gotest",
    "parse_log_gradle_custom",
    "parse_log_gradlew_v1",
    "parse_log_js",
    "parse_log_js_2",
    "parse_log_js_3",
    "parse_log_js_4",
    "parse_log_julia",
    "parse_log_junit",
    "parse_log_ocaml_v2",
    "parse_log_phpunit",
    "parse_log_pytest",
    "parse_log_r",
    "parse_log_scala_v2",
    "parse_log_swift",
}


class CohortValidationError(ValueError):
    """A lock or registry is unsafe or not reproducible."""


@dataclass(frozen=True)
class ValidatedCohort:
    """Bytes-bound cohort data safe to hand to a scored runner."""

    summary: Mapping[str, Any]
    tasks: tuple[Mapping[str, Any], ...]
    lock_sha256: str
    registry_sha256: str
    sealed_verifier_package_sha256: str


def _fail(path: str, message: str) -> None:
    raise CohortValidationError(f"{path}: {message}")


def _object(value: Any, path: str, allowed: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "must be an object")
    unknown = set(value) - allowed
    missing = allowed - set(value)
    if unknown:
        _fail(path, f"unknown fields: {sorted(unknown)}")
    if missing:
        _fail(path, f"missing fields: {sorted(missing)}")
    return value


def _string(value: Any, path: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        _fail(path, "must be a non-empty string")
    return value


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail(path, f"must be an integer >= {minimum}")
    return value


def _sha256(value: Any, path: str) -> str:
    text = _string(value, path)
    if not SHA256_RE.fullmatch(text):
        _fail(path, "must be a lowercase SHA-256")
    return text


def _git_sha(value: Any, path: str) -> str:
    text = _string(value, path)
    if not GIT_SHA_RE.fullmatch(text):
        _fail(path, "must be a 40-character lowercase Git SHA")
    return text


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail(path, "must be an array")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_repo(value: str) -> str:
    return value.strip().lower()


def _strict_hidden_field_scan(value: Any, path: str = "lock") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key.casefold() in HIDDEN_FIELD_NAMES:
                _fail(f"{path}.{key}", "hidden verifier field is forbidden in a lock")
            _strict_hidden_field_scan(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _strict_hidden_field_scan(child, f"{path}[{index}]")


def validate_registry(registry: Any) -> tuple[dict[str, set[str]], list[str]]:
    obj = _object(registry, "registry", REGISTRY_KEYS)
    if obj["schema_version"] != REGISTRY_SCHEMA:
        _fail("registry.schema_version", f"must equal {REGISTRY_SCHEMA!r}")
    _string(obj["registry_id"], "registry.registry_id")

    sources = _list(obj["source_digests"], "registry.source_digests")
    if not sources:
        _fail("registry.source_digests", "must not be empty")
    source_names: set[str] = set()
    for index, raw in enumerate(sources):
        source = _object(raw, f"registry.source_digests[{index}]", REGISTRY_SOURCE_KEYS)
        name = _string(source["name"], f"registry.source_digests[{index}].name")
        if name in source_names:
            _fail(f"registry.source_digests[{index}].name", "duplicate source name")
        source_names.add(name)
        _sha256(source["sha256"], f"registry.source_digests[{index}].sha256")

    index_by_kind = {kind: set() for kind in SUPPORTED_REGISTRY_KINDS}
    entries = _list(obj["entries"], "registry.entries")
    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(entries):
        entry = _object(raw, f"registry.entries[{index}]", REGISTRY_ENTRY_KEYS)
        kind = _string(entry["kind"], f"registry.entries[{index}].kind")
        if kind not in SUPPORTED_REGISTRY_KINDS:
            _fail(f"registry.entries[{index}].kind", "unsupported registry kind")
        source = _string(entry["source"], f"registry.entries[{index}].source")
        if source not in source_names:
            _fail(f"registry.entries[{index}].source", "unknown source name")
        value = _string(entry["value"], f"registry.entries[{index}].value")
        normalized = value.casefold() if kind in {
            "repo", "repo_pr", "repo_issue", "instance_id", "episode_id", "statement_token"
        } else value.lower()
        pair = (kind, normalized)
        if pair in seen:
            _fail(f"registry.entries[{index}]", "duplicate exclusion entry")
        seen.add(pair)
        index_by_kind[kind].add(normalized)
    return index_by_kind, sorted(source_names)


def _github_number(url: str, segment: str) -> int | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    try:
        marker = parts.index(segment)
        return int(parts[marker + 1])
    except (ValueError, IndexError):
        return None


def _github_repo(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc.casefold() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        return None
    return _canonical_repo(f"{parts[0]}/{parts[1]}")


def _overlap(kind: str, value: str, exclusions: Mapping[str, set[str]], path: str) -> None:
    normalized = value.casefold() if kind in {
        "repo", "repo_pr", "repo_issue", "instance_id", "episode_id", "statement_token"
    } else value.lower()
    if normalized in exclusions.get(kind, set()):
        _fail(path, f"overlaps exclusion registry kind {kind!r}")


def _validate_statement(statement: str, exclusions: Mapping[str, set[str]], path: str) -> None:
    if COMMIT_IN_TEXT_RE.search(statement):
        _fail(path, "contains a 40-character commit SHA")
    folded = statement.casefold()
    for token in exclusions.get("statement_token", set()):
        if token and token in folded:
            _fail(path, "contains a registry-provided hidden leakage token")


def _validate_task(
    raw: Any,
    index: int,
    mode: str,
    exclusions: Mapping[str, set[str]],
) -> tuple[str, str]:
    path = f"lock.tasks[{index}]"
    task = _object(raw, path, TASK_KEYS)
    rank = _integer(task["selection_rank"], f"{path}.selection_rank", minimum=1)
    if rank != index + 1:
        _fail(f"{path}.selection_rank", "must be contiguous and match task order")

    instance_id = _string(task["instance_id"], f"{path}.instance_id")
    if not INSTANCE_RE.fullmatch(instance_id):
        _fail(f"{path}.instance_id", "contains unsupported characters")
    _overlap("instance_id", instance_id, exclusions, f"{path}.instance_id")

    repo = _string(task["repo"], f"{path}.repo")
    if not REPO_RE.fullmatch(repo):
        _fail(f"{path}.repo", "must be owner/repository")
    canonical_repo = _canonical_repo(repo)
    _overlap("repo", canonical_repo, exclusions, f"{path}.repo")

    source = _object(task["source_identity"], f"{path}.source_identity", SOURCE_IDENTITY_KEYS)
    pr_url = _string(source["pr_url"], f"{path}.source_identity.pr_url")
    pr_number = _integer(source["pr_number"], f"{path}.source_identity.pr_number", minimum=1)
    if _github_number(pr_url, "pull") != pr_number:
        _fail(f"{path}.source_identity", "PR URL and PR number disagree")
    if _github_repo(pr_url) != canonical_repo:
        _fail(f"{path}.source_identity.pr_url", "PR repository disagrees with task repository")
    _overlap("repo_pr", f"{canonical_repo}#{pr_number}", exclusions, f"{path}.source_identity.pr_number")

    issue_urls = _list(source["issue_urls"], f"{path}.source_identity.issue_urls")
    for issue_index, issue_url_raw in enumerate(issue_urls):
        issue_url = _string(issue_url_raw, f"{path}.source_identity.issue_urls[{issue_index}]")
        issue_number = _github_number(issue_url, "issues")
        if issue_number is None:
            _fail(f"{path}.source_identity.issue_urls[{issue_index}]", "must be a GitHub issue URL")
        if _github_repo(issue_url) != canonical_repo:
            _fail(
                f"{path}.source_identity.issue_urls[{issue_index}]",
                "issue repository disagrees with task repository",
            )
        _overlap(
            "repo_issue",
            f"{canonical_repo}#{issue_number}",
            exclusions,
            f"{path}.source_identity.issue_urls[{issue_index}]",
        )

    merge_commit = _git_sha(source["merge_commit"], f"{path}.source_identity.merge_commit")
    _overlap("merge_commit", merge_commit, exclusions, f"{path}.source_identity.merge_commit")
    episode_ids = _list(source["episode_ids"], f"{path}.source_identity.episode_ids")
    for episode_index, episode_raw in enumerate(episode_ids):
        episode = _string(episode_raw, f"{path}.source_identity.episode_ids[{episode_index}]")
        _overlap("episode_id", episode, exclusions, f"{path}.source_identity.episode_ids[{episode_index}]")

    base_commit = _git_sha(task["base_commit"], f"{path}.base_commit")
    _overlap("base_commit", base_commit, exclusions, f"{path}.base_commit")
    statement = _string(task["problem_statement"], f"{path}.problem_statement")
    _validate_statement(statement, exclusions, f"{path}.problem_statement")
    language = _string(task["language"], f"{path}.language").casefold()
    _string(task["license"], f"{path}.license")
    if task["split"] != mode:
        _fail(f"{path}.split", f"must equal lock mode {mode!r}")

    image = _object(task["image"], f"{path}.image", IMAGE_KEYS)
    reference = _string(image["reference"], f"{path}.image.reference")
    digest = _string(image["digest"], f"{path}.image.digest")
    if not IMAGE_DIGEST_RE.fullmatch(digest):
        _fail(f"{path}.image.digest", "must be an immutable sha256 image digest")
    if not reference.endswith(f"@{digest}"):
        _fail(f"{path}.image.reference", "must end with the declared @sha256 digest")
    if image["platform"] != "linux/amd64":
        _fail(f"{path}.image.platform", "must equal 'linux/amd64'")
    workdir = _string(image["workdir"], f"{path}.image.workdir")
    if not workdir.startswith("/") or workdir == "/" or ".." in Path(workdir).parts:
        _fail(f"{path}.image.workdir", "must be a safe absolute repository workdir")

    _sha256(task["install_config_sha256"], f"{path}.install_config_sha256")
    _sha256(task["task_projection_sha256"], f"{path}.task_projection_sha256")

    fingerprints = _object(task["fingerprints"], f"{path}.fingerprints", FINGERPRINT_KEYS)
    for kind in FINGERPRINT_KEYS:
        value = _sha256(fingerprints[kind], f"{path}.fingerprints.{kind}")
        _overlap(kind, value, exclusions, f"{path}.fingerprints.{kind}")

    qualification = _object(task["qualification"], f"{path}.qualification", QUALIFICATION_KEYS)
    if qualification["status"] != "qualified":
        _fail(f"{path}.qualification.status", "must equal 'qualified' in a frozen lock")
    _sha256(qualification["receipt_sha256"], f"{path}.qualification.receipt_sha256")
    if qualification["base_fail_repeats"] != 2 or qualification["gold_pass_repeats"] != 2:
        _fail(f"{path}.qualification", "requires exactly two base-fail and two gold-pass repeats")

    timeout = _integer(task["verify_timeout_s"], f"{path}.verify_timeout_s", minimum=1)
    if timeout != 900:
        _fail(f"{path}.verify_timeout_s", "must equal the frozen 900-second timeout")
    log_parser = _string(task["log_parser"], f"{path}.log_parser")
    if log_parser not in SUPPORTED_LOG_PARSERS:
        _fail(f"{path}.log_parser", "parser is not in the vendored allowlist")
    return canonical_repo, language


def validate_lock(lock: Any, registry: Any) -> dict[str, Any]:
    """Validate a complete frozen lock and return a small safe summary."""

    _strict_hidden_field_scan(lock)
    obj = _object(lock, "lock", TOP_KEYS)
    if obj["schema_version"] != LOCK_SCHEMA:
        _fail("lock.schema_version", f"must equal {LOCK_SCHEMA!r}")
    _string(obj["cohort_id"], "lock.cohort_id")
    mode = obj["mode"]
    if mode not in {"pilot", "development"}:
        _fail("lock.mode", "must be 'pilot' or 'development'")

    source = _object(obj["source"], "lock.source", SOURCE_KEYS)
    if source["dataset"] != DATASET:
        _fail("lock.source.dataset", f"must equal {DATASET!r}")
    if source["revision"] != DATASET_REVISION:
        _fail("lock.source.revision", f"must equal pinned revision {DATASET_REVISION}")
    if source["split"] != "train":
        _fail("lock.source.split", "must equal upstream split 'train'")
    card_url = _string(source["dataset_card_url"], "lock.source.dataset_card_url")
    if card_url != f"https://huggingface.co/datasets/{DATASET}/tree/{DATASET_REVISION}":
        _fail("lock.source.dataset_card_url", "must be the immutable dataset revision URL")

    selection = _object(obj["selection"], "lock.selection", SELECTION_KEYS)
    if selection["policy_version"] != SELECTION_POLICY:
        _fail("lock.selection.policy_version", f"must equal {SELECTION_POLICY!r}")
    _integer(selection["seed"], "lock.selection.seed", minimum=0)
    expected = 24 if mode == "pilot" else 144
    expected_limits = (6, 12, 4) if mode == "pilot" else (8, 24, 8)
    if selection["expected_tasks"] != expected:
        _fail("lock.selection.expected_tasks", f"must equal {expected} for {mode}")
    for field, wanted in zip(
        ("min_languages", "min_repositories", "max_tasks_per_repo"), expected_limits
    ):
        if selection[field] != wanted:
            _fail(f"lock.selection.{field}", f"must equal frozen value {wanted}")

    registry_ref = _object(obj["exclusion_registry"], "lock.exclusion_registry", REGISTRY_REF_KEYS)
    _string(registry_ref["path"], "lock.exclusion_registry.path")
    _sha256(registry_ref["sha256"], "lock.exclusion_registry.sha256")
    sealed_ref = _object(
        obj["sealed_verifier_package"],
        "lock.sealed_verifier_package",
        REGISTRY_REF_KEYS,
    )
    _string(sealed_ref["path"], "lock.sealed_verifier_package.path")
    _sha256(sealed_ref["sha256"], "lock.sealed_verifier_package.sha256")

    parser = _object(obj["parser"], "lock.parser", PARSER_KEYS)
    if parser["source_repo"] != "https://github.com/SWE-rebench/SWE-rebench-V2":
        _fail("lock.parser.source_repo", "unexpected parser source repository")
    if parser["source_revision"] != PARSER_SOURCE_REVISION:
        _fail("lock.parser.source_revision", "unexpected parser source revision")
    _sha256(parser["vendored_parser_sha256"], "lock.parser.vendored_parser_sha256")

    exclusions, registry_sources = validate_registry(registry)
    tasks = _list(obj["tasks"], "lock.tasks")
    if len(tasks) != expected:
        _fail("lock.tasks", f"must contain exactly {expected} tasks")
    repos: Counter[str] = Counter()
    languages: Counter[str] = Counter()
    instance_ids: set[str] = set()
    base_commits: set[str] = set()
    projections: set[str] = set()
    for index, task in enumerate(tasks):
        repo, language = _validate_task(task, index, mode, exclusions)
        instance_id = task["instance_id"]
        base_commit = task["base_commit"]
        projection = task["task_projection_sha256"]
        if instance_id in instance_ids:
            _fail(f"lock.tasks[{index}].instance_id", "duplicate task ID")
        if base_commit in base_commits:
            _fail(f"lock.tasks[{index}].base_commit", "duplicate base commit")
        if projection in projections:
            _fail(f"lock.tasks[{index}].task_projection_sha256", "duplicate task projection")
        instance_ids.add(instance_id)
        base_commits.add(base_commit)
        projections.add(projection)
        repos[repo] += 1
        languages[language] += 1

    if len(languages) < selection["min_languages"]:
        _fail("lock.tasks", "insufficient language diversity")
    if len(repos) < selection["min_repositories"]:
        _fail("lock.tasks", "insufficient repository diversity")
    crowded = {repo: count for repo, count in repos.items() if count > selection["max_tasks_per_repo"]}
    if crowded:
        _fail("lock.tasks", f"repository cap exceeded: {crowded}")
    return {
        "cohort_id": obj["cohort_id"],
        "mode": mode,
        "tasks": len(tasks),
        "languages": len(languages),
        "repositories": len(repos),
        "registry_sources": registry_sources,
    }


def load_and_validate_lock(
    lock_path: str | Path,
    registry_path: str | Path,
    sealed_verifier_package_path: str | Path,
) -> ValidatedCohort:
    """The only supported loader for scored cohort locks.

    It binds the external registry bytes to the digest recorded in the lock.
    The future runner must also bind the sealed verifier package before model
    generation; this loader deliberately never opens that package.
    """

    lock_file = Path(lock_path)
    registry_file = Path(registry_path)
    sealed_file = Path(sealed_verifier_package_path)
    lock = json.loads(lock_file.read_text(encoding="utf-8"))
    registry = json.loads(registry_file.read_text(encoding="utf-8"))
    ref = lock.get("exclusion_registry")
    if not isinstance(ref, dict):
        _fail("lock.exclusion_registry", "must be an object")
    expected_name = ref.get("path")
    if expected_name != registry_file.name:
        _fail("lock.exclusion_registry.path", "must equal the supplied registry filename")
    expected_digest = ref.get("sha256")
    actual_digest = _sha256_file(registry_file)
    if expected_digest != actual_digest:
        _fail("lock.exclusion_registry.sha256", "does not match supplied registry bytes")
    sealed_ref = lock.get("sealed_verifier_package")
    if not isinstance(sealed_ref, dict):
        _fail("lock.sealed_verifier_package", "must be an object")
    if sealed_ref.get("path") != sealed_file.name:
        _fail("lock.sealed_verifier_package.path", "must equal the supplied package filename")
    sealed_digest = _sha256_file(sealed_file)
    if sealed_ref.get("sha256") != sealed_digest:
        _fail("lock.sealed_verifier_package.sha256", "does not match supplied package bytes")
    summary = validate_lock(lock, registry)
    projections = agent_projection(lock, registry)
    return ValidatedCohort(
        summary=summary,
        tasks=tuple(projections),
        lock_sha256=_sha256_file(lock_file),
        registry_sha256=actual_digest,
        sealed_verifier_package_sha256=sealed_digest,
    )


def _projection_body(task: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "instance_id": task["instance_id"],
        "repo": task["repo"],
        "base_commit": task["base_commit"],
        "problem_statement": task["problem_statement"],
        "language": task["language"],
        "verify_timeout_s": task["verify_timeout_s"],
    }


def agent_projection(lock: Any, registry: Any) -> list[dict[str, Any]]:
    """Validate the full lock, then emit only allowlisted model-visible fields."""

    validate_lock(lock, registry)
    projections = [_projection_body(task) for task in lock["tasks"]]
    for task, projection in zip(lock["tasks"], projections):
        rendered = json.dumps(projection, sort_keys=True, separators=(",", ":")).encode()
        if hashlib.sha256(rendered).hexdigest() != task["task_projection_sha256"]:
            _fail(
                f"lock.tasks[{task['selection_rank'] - 1}].task_projection_sha256",
                "does not match the allowlisted agent projection",
            )
    return projections


def canonical_projection_sha256(task: Mapping[str, Any]) -> str:
    """Return the digest used when freezing a safe agent projection."""

    rendered = json.dumps(_projection_body(task), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(rendered).hexdigest()


def dump_canonical_json(value: Any) -> bytes:
    """Canonical JSON bytes used for registry and receipt hashing."""

    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()
