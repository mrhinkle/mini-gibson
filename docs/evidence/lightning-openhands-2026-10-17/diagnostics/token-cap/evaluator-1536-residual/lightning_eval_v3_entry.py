#!/usr/bin/env python3
"""Select the pinned Lightning model, then enter this diagnostic evaluator."""

from __future__ import annotations

import runpy
from pathlib import Path

import agent_contract


agent_contract.MODEL = agent_contract.LIGHTNING_MODEL
agent_contract.MODEL_REVISION = agent_contract.LIGHTNING_REVISION
runpy.run_path(str(Path(__file__).with_name("eval_agent_v3.py")), run_name="__main__")
