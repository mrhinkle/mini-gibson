#!/usr/bin/env python3
"""Select the pinned Lightning model, then enter the 24-task evaluator."""

from __future__ import annotations

import runpy

import agent_contract


agent_contract.MODEL = agent_contract.LIGHTNING_MODEL
agent_contract.MODEL_REVISION = agent_contract.LIGHTNING_REVISION
runpy.run_path("/workspace/eval_agent_v3.py", run_name="__main__")
