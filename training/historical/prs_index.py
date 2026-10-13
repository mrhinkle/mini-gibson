"""Pull-request catalog for the historical join.

GraphQL pages are cached under the private trace cache. The normalized lists
match the inventory JSON the extractor already reads.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

ORG = "The-AIE"
REPOS = ("conference-os", "chatterbuilt", "the-gibson")

_QUERY = """
query($name: String!, $cursor: String) {
  repository(owner: "%s", name: $name) {
    pullRequests(first: 100, after: $cursor, orderBy: {field: UPDATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        state
        mergedAt
        createdAt
        headRefName
        title
        closingIssuesReferences(first: 20) {
          nodes { number url title repository { name } }
        }
      }
    }
  }
}
""" % ORG


def _gh_env() -> dict:
    env = os.environ.copy()
    env["GH_FORCE_TTY"] = "0"
    env["NO_COLOR"] = "1"
    env.pop("CLICOLOR_FORCE", None)
    return env


def _graphql(name: str, cursor: str | None) -> dict:
    command = ["gh", "api", "graphql", "-f", f"query={_QUERY}", "-f", f"name={name}"]
    if cursor:
        command.extend(["-f", f"cursor={cursor}"])
    else:
        command.extend(["-F", "cursor=null"])
    proc = subprocess.run(command, capture_output=True, text=True, timeout=90, env=_gh_env())
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "gh graphql failed")[:500])
    data = json.loads(proc.stdout)
    if data.get("errors"):
        raise RuntimeError(json.dumps(data["errors"])[:500])
    return data["data"]["repository"]["pullRequests"]


def normalize_pr(node: dict) -> dict:
    refs = []
    container = node.get("closingIssuesReferences") or {}
    for ref in container.get("nodes") or []:
        if not isinstance(ref, dict) or not isinstance(ref.get("number"), int):
            continue
        repo = ref.get("repository") or {}
        refs.append({
            "number": ref["number"],
            "url": ref.get("url") or "",
            "title": ref.get("title") or "",
            "repository": {"name": repo.get("name") or ""},
        })
    return {
        "number": node.get("number"),
        "state": node.get("state") or "",
        "mergedAt": node.get("mergedAt"),
        "createdAt": node.get("createdAt"),
        "headRefName": node.get("headRefName") or "",
        "title": node.get("title") or "",
        "closingIssuesReferences": refs,
    }


def fetch_repo(name: str, cache_dir: Path, pause_s: float = 0.2) -> list[dict]:
    """Fetch every pull request and cache the raw pages plus the normalized list."""
    pages = cache_dir / "prs-v2" / name
    pages.mkdir(parents=True, exist_ok=True)
    cursor = None
    prs: list[dict] = []
    seen: set[int] = set()
    for page in range(1, 80):
        payload = _graphql(name, cursor)
        raw_path = pages / f"page-{page:02d}.json"
        raw_path.write_text(json.dumps(payload), encoding="utf-8")
        os.chmod(raw_path, 0o600)
        for node in payload.get("nodes") or []:
            if not isinstance(node, dict) or not isinstance(node.get("number"), int):
                continue
            if node["number"] in seen:
                continue
            seen.add(node["number"])
            prs.append(normalize_pr(node))
        info = payload.get("pageInfo") or {}
        if not info.get("hasNextPage"):
            break
        cursor = info.get("endCursor")
        if not cursor:
            break
        time.sleep(pause_s)
    return prs


def write_catalog(prs_dir: Path, cache_dir: Path) -> dict[str, int]:
    """Refresh all three repos. Returns pull-request counts."""
    if not _under_trace(prs_dir) or not _under_trace(cache_dir):
        raise PermissionError("PR catalog must stay under the trace root")
    prs_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in REPOS:
        prs = fetch_repo(name, cache_dir)
        path = prs_dir / f"prs.{name}.json"
        path.write_text(json.dumps(prs), encoding="utf-8")
        os.chmod(path, 0o600)
        counts[name] = len(prs)
    return counts


def _under_trace(path: Path) -> bool:
    resolved = path.expanduser().resolve()
    root = (Path.home() / "gibson-traces").resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return False
    return True


def load_catalog(prs_dir: Path) -> dict[str, list[dict]]:
    loaded = {}
    for name in REPOS:
        path = prs_dir / f"prs.{name}.json"
        loaded[name] = json.loads(path.read_text(encoding="utf-8"))
    return loaded
