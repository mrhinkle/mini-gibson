#!/usr/bin/env python3
"""Deterministic unit checks for parsing and evaluator artifact filtering."""

from pathlib import Path
from tempfile import TemporaryDirectory

from eval_agent_v3 import parse_call, select_locked_tasks, text_snapshot, tree_hashes


CASES = [
    (
        '<tool_call>{"name":"execute_bash","arguments":{"command":"ls"}}</tool_call>',
        {"name": "execute_bash", "arguments": {"command": "ls"}},
    ),
    (
        "\n<tool_call>\n<function=execute_bash>\n<parameter=command>\n"
        "find . -type f\n</parameter>\n</function>\n</tool_call>\n<|im_end|>",
        {"name": "execute_bash", "arguments": {"command": "find . -type f"}},
    ),
    (
        "<tool_call>\n<function=str_replace_editor>\n"
        "<parameter=command>view</parameter>\n"
        "<parameter=path>bounds.py</parameter>\n"
        "<parameter=view_range>[1, 20]</parameter>\n"
        "</function>\n</tool_call>",
        {
            "name": "str_replace_editor",
            "arguments": {"command": "view", "path": "bounds.py", "view_range": [1, 20]},
        },
    ),
    (
        "<tool_call>\n<function=str_replace_editor>\n"
        "<parameter=command>str_replace</parameter>\n"
        "<parameter=path>example.py</parameter>\n"
        "<parameter=old_str>\n        return value\n</parameter>\n"
        "<parameter=new_str>\n    return value\n</parameter>\n"
        "</function>\n</tool_call>\n<|im_end|>",
        {
            "name": "str_replace_editor",
            "arguments": {
                "command": "str_replace",
                "path": "example.py",
                "old_str": "        return value",
                "new_str": "    return value",
            },
        },
    ),
]


for text, expected in CASES:
    parsed, public = parse_call(text)
    assert parsed == expected, (parsed, expected)
    assert public == "", public

with TemporaryDirectory() as raw_root:
    root = Path(raw_root)
    (root / "solution.py").write_text("value = 1\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_solution.py").write_text("def test_solution(): pass\n")
    (root / "pytest_cache").mkdir()
    (root / "pytest_cache" / "not-ignored.txt").write_text("protected\n")
    (root / ".pytest_cache" / "v" / "cache").mkdir(parents=True)
    (root / ".pytest_cache" / "v" / "cache" / "nodeids").write_text("[]\n")
    (root / "tests" / "__pycache__").mkdir()
    (root / "tests" / "__pycache__" / "test_solution.pyc").write_bytes(b"bytecode")
    expected = {"solution.py", "tests/test_solution.py", "pytest_cache/not-ignored.txt"}
    assert set(tree_hashes(root)) == expected
    assert set(text_snapshot(root)) == expected

locked = ["fresh-c-roman-numeral", "fresh-d-pagination-slice"]
assert select_locked_tasks({"evaluation_task_ids": locked}, None) == locked
assert select_locked_tasks({}, locked) == locked
try:
    select_locked_tasks({"evaluation_task_ids": locked}, list(reversed(locked)))
except ValueError as exc:
    assert "exactly match" in str(exc)
else:
    raise AssertionError("mismatched task selection was not rejected")

print(
    f"HARNESS_UNIT_PASS parse_cases={len(CASES)} artifact_filters=2 "
    "protected_files=3 locked_selection=3"
)
