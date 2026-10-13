"""Fail-closed redaction for historical SFT records.

Secrets are replaced. A record that still matches a secret pattern after
replacement is dropped by the caller. Match text is never returned.

Usage: python3 training/historical/redact.py
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from typing import Any

# Longer names first so a short token is not left inside an FQDN.
HOSTNAMES = (
    "MacBook-Pro-4.local",
    "Marks-Mac-mini.local",
    "MacBook-Pro-4",
    "Marks-Mac-mini",
)

_PEM = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
# A URL broken by a newline still has the userinfo or port on the next line.
# One whitespace run only, so this cannot swallow the rest of a tool result.
_CONN_SPLIT = re.compile(
    r"(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://(?!<redacted>)[^\s\"']*\s+[^\s\"']*[@:][^\s\"']*",
    re.IGNORECASE,
)
_CONN = re.compile(
    r"(postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://(?!<redacted>)[^\s\"']+",
    re.IGNORECASE,
)
_USERINFO = re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@")
_BEARER = re.compile(r"([Bb]earer)\s+[A-Za-z0-9._~+/=-]{12,}")
_KEY = re.compile(
    r"(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{22,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
)
_OP = re.compile(r"op://[^\s\"'`<>]+")
_ENV = re.compile(
    r"(?P<head>[A-Za-z_][A-Za-z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)[A-Za-z0-9_]*"
    r"(?:[\"']?\s*[:=]\s*[\"']?))"
    r"(?!<redact)(?!<email)(?P<val>[^\s\"',}<]{6,})",
    re.IGNORECASE,
)
# A backslash before the dot is how a Signed-off-by check is written in a
# shell regex (user@domain\.tld). The domain label may already be <host>.
_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\\?\.)+[A-Za-z]{2,}"
    r"|[A-Za-z0-9._%+-]+@<(?:host|user)>(?:\\?\.[A-Za-z]{2,})?",
    re.IGNORECASE,
)
# The username part is optional so a bare `/Users/` in a regex or a sentence
# is rewritten too. `/Users/<user>` does not match again.
_HOME = re.compile(r"(?i)/(Users|home)/(?!<user>)(?:[A-Za-z0-9._%-]+)?")
_HOME_ENC = re.compile(r"(?i)%2F(Users|home)%2F(?!<user>)(?:[A-Za-z0-9._%-]+)?")
# Substring, not a word boundary. Hyphens and underscores are how the name
# survives inside tokens (`mrhinkle-authored`, `broker-mrhinkle`, `mrhinkle_cortex`).
_USERNAME = re.compile(r"mrhinkle|markhinkle", re.IGNORECASE)
_HOST = re.compile("|".join(re.escape(h) for h in HOSTNAMES))
_DOTENV_ARG = re.compile(r"(^|[\\/\"'\s])\.env\b")
# Claude session dirs and the slash-to-hyphen encoding of an absolute path.
_TMP_CLAUDE = re.compile(r"(?:/private)?/tmp/claude-(?:[A-Za-z0-9._+-]|/)+")
# Bounded so a long hyphenated line cannot make the matcher quadratic.
_USERS_PATH_ENC = re.compile(r"-Users-(?:[A-Za-z0-9._+-]{1,80}-){1,40}[A-Za-z0-9._+-]{1,80}")
# Prefixes that are secrets even when the rest of the token was split by a regex.
_GHP_PREFIX = re.compile(r"gh[pousr]_")
_GITHUB_PAT_PREFIX = re.compile(r"github_pat_")
_AKIA_PREFIX = re.compile(r"AKIA")
_SK_PREFIX = re.compile(r"(?<![A-Za-z0-9])sk-")
_PRIVATE_WORD = re.compile(r"PRIVATE KEY")
_HOME_LISTING = "[home directory listing removed]"
_SPLIT_CMD = re.compile(r"&&|\|\||[;&|\n]")
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=$")
_HOME_OPERAND = re.compile(r"/(?:Users|home)/[A-Za-z0-9._%-]+/?")

# Residual detectors. Replacements above are written so they do not match these.
RESIDUAL = (
    ("private_key", _PEM),
    ("connection_string", _CONN),
    ("url_userinfo", _USERINFO),
    ("bearer", _BEARER),
    ("api_key", _KEY),
    ("onepassword", _OP),
    ("env_assignment", _ENV),
    ("email", _EMAIL),
    ("username", _USERNAME),
    ("home_path", _HOME),
    ("home_path_encoded", _HOME_ENC),
    ("hostname", _HOST),
    ("token_prefix", _GHP_PREFIX),
    ("github_pat_prefix", _GITHUB_PAT_PREFIX),
    ("akia_prefix", _AKIA_PREFIX),
    ("sk_prefix", _SK_PREFIX),
    ("private_key_word", _PRIVATE_WORD),
)


def _home_sub(match: re.Match) -> str:
    kind = "home" if match.group(1).lower() == "home" else "Users"
    return f"/{kind}/<user>"


def _home_enc_sub(match: re.Match) -> str:
    kind = "home" if match.group(1).lower() == "home" else "Users"
    return f"%2F{kind}%2F<user>"


def redact_text(text: str) -> str:
    """Replace secret-shaped substrings. Idempotent on its own output."""
    if not text:
        return text
    text = text.replace("\x00", "")
    text = _PEM.sub("<redacted-private-key>", text)
    text = _CONN_SPLIT.sub(r"\1://<redacted>", text)
    text = _CONN.sub(r"\1://<redacted>", text)
    text = _USERINFO.sub(r"\1<redacted>@", text)
    text = _BEARER.sub(r"\1 <redacted>", text)
    text = _KEY.sub("<redacted-key>", text)
    text = _OP.sub("<redacted-op>", text)
    text = _ENV.sub(lambda m: m.group("head") + "<redacted>", text)
    text = _GHP_PREFIX.sub("<redacted-key>", text)
    text = _GITHUB_PAT_PREFIX.sub("<redacted-key>", text)
    text = _AKIA_PREFIX.sub("<redacted-key>", text)
    # A bare sk- prefix, not the letters inside task-, risk-, ask-, disk-, or mask-.
    text = _SK_PREFIX.sub("<redacted-key>", text)
    text = _PRIVATE_WORD.sub("<redacted-private-key>", text)
    text = _EMAIL.sub("<email>", text)
    # Collapse session dirs before the username substring, or the name inside
    # `-Users-mrhinkle-...` becomes `<user>` and the path encoding no longer matches.
    text = _TMP_CLAUDE.sub("<tmp>", text)
    text = _USERS_PATH_ENC.sub("<tmp>", text)
    text = _HOME.sub(_home_sub, text)
    text = _HOME_ENC.sub(_home_enc_sub, text)
    text = _USERNAME.sub("<user>", text)
    text = _HOST.sub("<host>", text)
    # Username@hostname becomes <user>@<host> only after both replacements.
    text = _EMAIL.sub("<email>", text)
    return text


def residual_names(text: str) -> list[str]:
    """Pattern names still present. Never the matched text."""
    if not text:
        return []
    return [name for name, rx in RESIDUAL if rx.search(text)]


def residual_object(obj: Any) -> list[str]:
    """Pattern names in decoded strings. JSON escapes are not part of the text."""
    found: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, str):
            for name in residual_names(value):
                if name not in found:
                    found.append(name)
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(key, str):
                    for name in residual_names(key):
                        if name not in found:
                            found.append(name)
                walk(item)
            return
        if isinstance(value, list):
            for item in value:
                walk(item)

    walk(obj)
    return found


def residual_json_text(text: str) -> list[str]:
    """Scan one JSON document by its decoded strings.

    A raw JSON line turns a newline into backslash-n and a quote into
    backslash-quote. Those extra characters complete secret patterns that
    are not in the text (a bare scheme, a short assignment, an @filename).
    Invalid JSON is scanned raw so a broken line still fails closed.
    """
    stripped = text.lstrip()
    if not stripped or stripped[0] not in "{[":
        return residual_names(text)
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return residual_names(text)
    if isinstance(obj, (dict, list)):
        return residual_object(obj)
    if isinstance(obj, str):
        return residual_names(obj)
    return []


def _map_strings(obj: Any, fn) -> Any:
    if isinstance(obj, str):
        return fn(obj)
    if isinstance(obj, list):
        return [_map_strings(item, fn) for item in obj]
    if isinstance(obj, dict):
        return {
            (fn(key) if isinstance(key, str) else key): _map_strings(value, fn)
            for key, value in obj.items()
        }
    return obj


def _unwrap_token(token: str) -> str:
    raw = token.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1]
    return raw.replace("\\ ", " ")


def _is_home_operand(token: str) -> bool:
    """True when the operand is the home directory itself, not a child path."""
    raw = _unwrap_token(token)
    if raw in {"~", "~/", "$HOME", "$HOME/", "${HOME}", "${HOME}/"}:
        return True
    return _HOME_OPERAND.fullmatch(raw) is not None


def _command_strings(arguments: str) -> list[str]:
    text = arguments or ""
    try:
        obj = json.loads(text) if text.lstrip()[:1] in "{[" else None
    except json.JSONDecodeError:
        obj = None
    if isinstance(obj, dict):
        found = []
        for key in ("command", "cmd", "script"):
            value = obj.get(key)
            if isinstance(value, str) and value:
                found.append(value)
        return found
    return [text] if text else []


def command_lists_home(command: str) -> bool:
    """True for `ls ~` or `find ~ -maxdepth` (home itself, not a subdirectory).

    Tokenizing uses str.split. A quoted-string regex here backtracked on
    real tool commands and stalled the extract.
    """
    if not command or ("ls" not in command and "find" not in command):
        return False
    for segment in _SPLIT_CMD.split(command):
        tokens = segment.split()
        index = 0
        while index < len(tokens) and _ENV_ASSIGN.match(_unwrap_token(tokens[index])):
            index += 1
        if index >= len(tokens):
            continue
        word = _unwrap_token(tokens[index])
        if word in {"command", "sudo", "time"} and index + 1 < len(tokens):
            index += 1
            word = _unwrap_token(tokens[index])
        word = word.rsplit("/", 1)[-1]
        if word not in {"ls", "find"}:
            continue
        operands = [tok for tok in tokens[index + 1:] if not _unwrap_token(tok).startswith("-")]
        if not any(_is_home_operand(tok) for tok in operands):
            continue
        if word == "ls":
            return True
        if "-maxdepth" in segment:
            return True
    return False


def wipe_home_listings(messages: list[dict]) -> list[dict]:
    """Replace tool output of a home-directory listing. Mutates the list."""
    listing_ids: set[str] = set()
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            blob = "\n".join(_command_strings(str(fn.get("arguments") or "")))
            if command_lists_home(blob):
                cid = call.get("id")
                if cid:
                    listing_ids.add(cid)
    if not listing_ids:
        return messages
    for message in messages:
        if message.get("role") == "tool" and message.get("tool_call_id") in listing_ids:
            message["content"] = _HOME_LISTING
    return messages


def wipe_dotenv_results(messages: list[dict]) -> list[dict]:
    """Replace tool output whose call read a .env file."""
    messages = copy.deepcopy(messages)
    env_ids: set[str] = set()
    for message in messages:
        if message.get("role") != "assistant":
            continue
        for call in message.get("tool_calls") or []:
            fn = (call.get("function") or {})
            blob = f"{fn.get('name') or ''} {fn.get('arguments') or ''}"
            if _DOTENV_ARG.search(blob):
                cid = call.get("id")
                if cid:
                    env_ids.add(cid)
    if not env_ids:
        return messages
    for message in messages:
        if message.get("role") == "tool" and message.get("tool_call_id") in env_ids:
            message["content"] = "[.env contents redacted]"
    return messages


def redact_record(record: dict) -> tuple[dict, list[str]]:
    """Return a redacted copy and any residual pattern names."""
    cleaned = copy.deepcopy(record)
    if isinstance(cleaned.get("messages"), list):
        cleaned["messages"] = wipe_dotenv_results(cleaned["messages"])
        wipe_home_listings(cleaned["messages"])
    cleaned = _map_strings(cleaned, lambda s: redact_text(s) if isinstance(s, str) else s)
    hits = residual_object(cleaned)
    return cleaned, hits


def drop_if_residual(record: dict) -> tuple[dict | None, list[str]]:
    """Drop a record that still matches. Does not redact again."""
    hits = residual_object(record)
    if hits:
        return None, hits
    return record, []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python3 training/historical/redact.py",
        usage="python3 training/historical/redact.py",
        description=(
            "Library for fail-closed redaction. Import redact_text or redact_record. "
            "Running this file prints usage."
        ),
    )
    parser.parse_args(argv)
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
