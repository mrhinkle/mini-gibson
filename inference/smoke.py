"""Fixture-default structured-tool smoke. Not Gibson conformance and not a score.

Live HTTP runs only with --mode live and an explicit endpoint. No credentials,
no environment reads, no default host. full_training and tool_conformance stay NO_GO.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request

TOOL = "gibson_smoke"
MAX_BODY = 1_000_000
_USAGE_KEYS = ("prompt_tokens", "completion_tokens", "total_tokens")
_USAGE_ERR = {"fixture_args", "live_args", "bad_endpoint", "fixture_missing", "output_exists"}


class SmokeError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def dumps(obj: object) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def digest(raw: bytes | None) -> str | None:
    return None if raw is None else hashlib.sha256(raw).hexdigest()


def build_request(model: str, nonce: str) -> dict:
    return {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": f"Call {TOOL} with nonce {nonce}. Format smoke only."}],
        "tools": [{
            "type": "function",
            "function": {
                "name": TOOL,
                "description": "DEV parser smoke. Echo nonce. Not a Gibson runtime tool.",
                "parameters": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {"nonce": {"type": "string"}},
                    "required": ["nonce"],
                },
            },
        }],
        "tool_choice": {"type": "function", "function": {"name": TOOL}},
    }


def _obj(payload: object, code: str) -> dict:
    if not isinstance(payload, dict):
        raise SmokeError(code)
    return payload


def check_models(payload: object, model: str) -> None:
    data = _obj(payload, "malformed_models").get("data")
    if not isinstance(data, list):
        raise SmokeError("malformed_models")
    ids = []
    for item in data:
        if not isinstance(item, dict):
            raise SmokeError("malformed_models")
        mid = item.get("id")
        if not isinstance(mid, str) or not mid.strip():
            raise SmokeError("malformed_models")
        ids.append(mid)
    if model not in ids:
        raise SmokeError("model_missing")


def parse_arguments(raw: object) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raise SmokeError("malformed_arguments") from None
    if not isinstance(raw, dict):
        raise SmokeError("arguments_not_object")
    return raw


def check_completion(payload: object, model: str, nonce: str) -> str:
    body = _obj(payload, "bad_completion")
    if body.get("model") != model:
        raise SmokeError("response_model_mismatch")
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices or choices[0] is None:
        raise SmokeError("empty_choices")
    if len(choices) != 1 or not isinstance(choices[0], dict):
        raise SmokeError("multiple_choices")
    message = choices[0].get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise SmokeError("not_assistant")
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or not calls:
        raise SmokeError("prose_only" if isinstance(message.get("content"), str) else "missing_tool_call")
    if len(calls) != 1 or not isinstance(calls[0], dict):
        raise SmokeError("multiple_calls")
    call = calls[0]
    if not isinstance(call.get("id"), str) or not call["id"].strip():
        raise SmokeError("empty_id")
    fn = call.get("function")
    if call.get("type") != "function" or not isinstance(fn, dict) or fn.get("name") != TOOL:
        raise SmokeError("unexpected_function")
    args = parse_arguments(fn.get("arguments"))
    if set(args) != {"nonce"} or not isinstance(args.get("nonce"), str):
        raise SmokeError("bad_arguments")
    if args["nonce"] != nonce:
        raise SmokeError("nonce_mismatch")
    return model


def finite_usage(payload: object) -> tuple[str, dict | None]:
    if not isinstance(payload, dict) or "usage" not in payload or payload["usage"] is None:
        return "unavailable", None
    usage = payload["usage"]
    if not isinstance(usage, dict):
        raise SmokeError("bad_usage")
    out = {}
    for key in _USAGE_KEYS:
        value = usage.get(key)
        bad = key not in usage or isinstance(value, bool) or not isinstance(value, (int, float))
        bad = bad or (isinstance(value, float) and not math.isfinite(value)) or value < 0
        if bad:
            raise SmokeError("bad_usage")
        out[key] = value
    return "present", out


def base_receipt(mode: str, model: str, claimed: str | None) -> dict:
    return {
        "ok": False,
        "mode": mode,
        "live_inference": False,
        "measured_inference": False,
        "score": "NOT_SCORED",
        "stages": {"full_training": "NO_GO", "tool_conformance": "NO_GO"},
        "selected_model": model,
        "response_model": None,
        "nonce_fulfilled": False,
        "http_success": None if mode == "fixture" else False,
        "request_sha256": None,
        "response_sha256": None,
        "usage": None,
        "usage_status": "unavailable",
        "pins": {
            "observed": {"served_model_present": False, "response_model": None},
            "operator_claimed": {"model_revision": claimed},
            "model_revision_verified": False,
        },
        "error": None,
    }


def evaluate(mode, model, nonce, models_payload, completion, claimed, request_raw, response_raw, http_success, live_http):
    receipt = base_receipt(mode, model, claimed)
    receipt["request_sha256"] = digest(request_raw)
    receipt["response_sha256"] = digest(response_raw)
    receipt["http_success"] = None if mode == "fixture" else bool(http_success)
    receipt["live_inference"] = bool(mode == "live" and live_http)
    try:
        check_models(models_payload, model)
        receipt["pins"]["observed"]["served_model_present"] = True
        receipt["response_model"] = check_completion(completion, model, nonce)
        receipt["pins"]["observed"]["response_model"] = receipt["response_model"]
        receipt["usage_status"], receipt["usage"] = finite_usage(completion)
    except SmokeError as exc:
        receipt["error"] = exc.code
        if isinstance(completion, dict) and isinstance(completion.get("model"), str):
            receipt["response_model"] = completion["model"]
            receipt["pins"]["observed"]["response_model"] = completion["model"]
        return receipt
    receipt["nonce_fulfilled"] = True
    receipt["ok"] = mode == "fixture" or http_success is True
    return receipt


def endpoint_origin(url: str) -> str:
    if not isinstance(url, str) or not url.strip() or any(ch in url for ch in "\r\n\t"):
        raise SmokeError("bad_endpoint")
    try:
        parts = urllib.parse.urlsplit(url.strip())
        hostname = parts.hostname
        port = parts.port
        username = parts.username
        password = parts.password
    except ValueError:
        raise SmokeError("bad_endpoint") from None
    if parts.scheme not in {"http", "https"} or not hostname:
        raise SmokeError("bad_endpoint")
    if username or password or parts.query or parts.fragment or "@" in parts.netloc:
        raise SmokeError("bad_endpoint")
    if parts.path.rstrip("/") not in {"", "/v1"}:
        raise SmokeError("bad_endpoint")
    host = f"[{hostname}]" if ":" in hostname else hostname
    netloc = host if port is None else f"{host}:{port}"
    return f"{parts.scheme}://{netloc}"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def http_call(method: str, url: str, body: bytes | None, timeout: float) -> tuple[int, bytes]:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    # Empty proxy map: build_opener's default ProxyHandler would call getproxies().
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw, status = resp.read(MAX_BODY + 1), getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        raw, status = exc.read(MAX_BODY + 1), exc.code
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        timed = isinstance(exc, (socket.timeout, TimeoutError)) or isinstance(reason, (socket.timeout, TimeoutError))
        raise SmokeError("timed_out" if timed else "connection_failed") from None
    if len(raw) > MAX_BODY:
        raise SmokeError("response_too_large")
    return status, raw


def load_json(raw: bytes) -> object:
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise SmokeError("bad_json") from None


def run_fixture(model: str, nonce: str, models_payload: object, completion: object, claimed: str | None = None) -> dict:
    return evaluate(
        "fixture", model, nonce, models_payload, completion, claimed,
        dumps(build_request(model, nonce)), dumps(completion), None, False,
    )


def run_live(endpoint: str, model: str, nonce: str, timeout: float, claimed: str | None = None) -> dict:
    origin = endpoint_origin(endpoint)
    request_raw = dumps(build_request(model, nonce))
    receipt = base_receipt("live", model, claimed)
    receipt["request_sha256"] = digest(request_raw)
    try:
        mstatus, mraw = http_call("GET", origin + "/v1/models", None, timeout)
    except SmokeError as exc:
        receipt["error"] = exc.code
        return receipt
    if mstatus != 200:
        receipt.update(live_inference=True, error="http_status", response_sha256=digest(mraw))
        return receipt
    try:
        models_payload = load_json(mraw)
        cstatus, craw = http_call("POST", origin + "/v1/chat/completions", request_raw, timeout)
    except SmokeError as exc:
        receipt.update(live_inference=True, error=exc.code, response_sha256=digest(mraw))
        return receipt
    receipt.update(live_inference=True, response_sha256=digest(craw))
    if cstatus != 200:
        receipt["error"] = "http_status"
        return receipt
    try:
        completion = load_json(craw)
    except SmokeError as exc:
        receipt["error"] = exc.code
        return receipt
    return evaluate("live", model, nonce, models_payload, completion, claimed, request_raw, craw, True, True)


def write_receipt(receipt: dict, path: str | None) -> None:
    text = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if path is None:
        sys.stdout.write(text)
        return
    if os.path.lexists(path):
        raise SmokeError("output_exists")
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)


def _timeout(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("bad timeout") from None
    if not math.isfinite(number) or not 0 < number <= 300:
        raise argparse.ArgumentTypeError("bad timeout")
    return number


def _read_json(path: str) -> object:
    try:
        with open(path, "rb") as handle:
            raw = handle.read(MAX_BODY + 1)
    except OSError:
        raise SmokeError("fixture_missing") from None
    if len(raw) > MAX_BODY:
        raise SmokeError("response_too_large")
    return load_json(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Structured-tool smoke. Default mode is offline fixture.")
    parser.add_argument("--mode", choices=("fixture", "live"), default="fixture")
    parser.add_argument("--model", required=True)
    parser.add_argument("--nonce")
    parser.add_argument("--endpoint")
    parser.add_argument("--fixture-models")
    parser.add_argument("--fixture-completion")
    parser.add_argument("--claimed-revision")
    parser.add_argument("--timeout", type=_timeout, default=30.0)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        if args.output and os.path.lexists(args.output):
            raise SmokeError("output_exists")
        if args.mode == "fixture":
            if args.endpoint or not args.nonce or not args.fixture_models or not args.fixture_completion:
                raise SmokeError("fixture_args")
            receipt = run_fixture(
                args.model, args.nonce, _read_json(args.fixture_models),
                _read_json(args.fixture_completion), args.claimed_revision,
            )
        else:
            if not args.endpoint or args.fixture_models or args.fixture_completion:
                raise SmokeError("live_args")
            receipt = run_live(
                args.endpoint, args.model, args.nonce or secrets.token_hex(16),
                args.timeout, args.claimed_revision,
            )
        write_receipt(receipt, args.output)
    except SmokeError as exc:
        fail = base_receipt(args.mode, args.model, args.claimed_revision)
        fail["error"] = exc.code
        write_receipt(fail, None if exc.code == "output_exists" else args.output)
        return 2 if exc.code in _USAGE_ERR else 1
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
