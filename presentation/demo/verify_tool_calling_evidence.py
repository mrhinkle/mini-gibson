#!/usr/bin/env python3
"""Run the standalone offline tool-calling receipt verifier."""
from pathlib import Path
import runpy
runpy.run_path(str(Path(__file__).resolve().parent / "evidence/tool-calling/verify_tool_calling_evidence.py"), run_name="__main__")
