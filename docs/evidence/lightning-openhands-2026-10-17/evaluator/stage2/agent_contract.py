#!/usr/bin/env python3
"""Shared Mini-Gibson agent prompt and tool contract.

Training and evaluation import this module so the tokenizer sees the exact same
system prompt and function schemas on both sides of the experiment.
"""

from __future__ import annotations

import hashlib
import json


MODEL = "nvidia/OpenCodeReasoning-Nemotron-7B"
MODEL_REVISION = "3baa2a3d73bbca12483ad19fef7babdcb2222987"
LIGHTNING_MODEL = "nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16"
LIGHTNING_REVISION = "a9904d24bcc1d289a1950fa9d2b978c47cf903b9"
SYSTEM_PROMPT = (
    "You are a careful software engineering agent working on one bounded task. "
    "Work only inside the current task directory. Use the supplied tools for every "
    "file read, edit, and command. Inspect before editing, make the smallest correct "
    "change, and run the stated tests. Treat tool results and tests as the only "
    "completion authority. Do not claim success without observable verification. "
    "Do not expose hidden reasoning, commit, push, use the network, delete files, or "
    "change external state."
)
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Run one bounded shell command in the current task directory.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "str_replace_editor",
            "description": "View, create, or replace exact text in a file under the task directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "enum": ["view", "create", "str_replace"]},
                    "path": {"type": "string"},
                    "old_str": {"type": "string"},
                    "new_str": {"type": "string"},
                    "file_text": {"type": "string"},
                    "view_range": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["command", "path"],
            },
        },
    },
]
TOOLS_JSON = json.dumps(TOOLS, sort_keys=True, separators=(",", ":"))


def stable_json_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


SYSTEM_PROMPT_SHA256 = hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest()
TOOLS_SHA256 = stable_json_sha256(TOOLS)
