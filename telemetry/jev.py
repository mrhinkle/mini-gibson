"""Append-only decision metadata for a run-owned JSONL artifact."""
from pathlib import Path
from adapters.jev import canonical_json


class JevJsonlTelemetry:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def __call__(self, event: dict) -> None:
        # Parent/run layout is the runner's responsibility. Never truncate an existing receipt.
        with self.path.open("a", encoding="utf-8") as target:
            target.write(canonical_json(event) + "\n")
