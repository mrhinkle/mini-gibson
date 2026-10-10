#!/usr/bin/env python3
"""Direct OpenRouter smoke (no Hermes): list Nemotron, check key, optional chat.

Does NOT implement a full tool-using agent loop. Use Hermes runner or
Codex/Claude computer-use prompts for real observational traces.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def key() -> str:
    k = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not k:
        raise SystemExit("OPENROUTER_API_KEY missing")
    return k


def get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {key()}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def post(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key()}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/mrhinkle/mini-gibson",
            "X-Title": "mini-gibson-433-smoke",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("OBS_MODEL", "nvidia/nemotron-3.5-lightning"))
    ap.add_argument("--provider", default=os.environ.get("OBS_PROVIDER_PIN", "CoreWeave"))
    ap.add_argument("--chat", action="store_true", help="send a 1-token chat completion")
    args = ap.parse_args()

    info = get("https://openrouter.ai/api/v1/key")["data"]
    print("key_ok", {k: info.get(k) for k in ("label", "limit", "limit_remaining", "usage") if k in info or True})
    print("limit_remaining", info.get("limit_remaining"))
    print("usage", info.get("usage"))

    models = get("https://openrouter.ai/api/v1/models")["data"]
    hits = [m["id"] for m in models if "nemotron" in m["id"].lower()]
    print("nemotron_models", hits[:20])
    if args.model not in hits and not any(args.model == h for h in hits):
        print(f"WARN model {args.model} not in listing (may still work)", file=sys.stderr)

    if args.chat:
        body = {
            "model": args.model,
            "messages": [{"role": "user", "content": "Reply with exactly: pong"}],
            "max_tokens": 8,
            "provider": {"only": [args.provider], "require_parameters": True},
        }
        out = post("https://openrouter.ai/api/v1/chat/completions", body)
        print("chat_id", out.get("id"))
        print("provider_meta", out.get("provider"))
        choice = (out.get("choices") or [{}])[0]
        print("content", (choice.get("message") or {}).get("content"))
        print("usage", out.get("usage"))
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
