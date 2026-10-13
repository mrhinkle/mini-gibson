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
# 8 characters of token is enough to drop. A bearer cut shorter than 12
# still has the shape, and the window is fail-closed if it survives.
_BEARER = re.compile(r"([Bb]earer)\s+[A-Za-z0-9._~+/=-]{8,}")
_KEY = re.compile(
    r"(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{22,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|xox[baprs]-[A-Za-z0-9-]{10,}"
    r"|eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"
)
# A known secret shape at least 8 characters long, shorter than the full
# token above. The whole prefix is replaced. A leftover of this shape is residual.
_TRUNC_KEY = re.compile(
    r"gh[pousr]_[A-Za-z0-9]{4,}"
    r"|github_pat_[A-Za-z0-9_]*"
    r"|AKIA[0-9A-Z]{4,}"
    r"|(?<![A-Za-z0-9])(?:sk|pk|rk)-(?:ant-|or-|proj-)?[A-Za-z0-9_-]{5,}"
    r"|xox[baprs]-[A-Za-z0-9-]{4,}"
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
# Absolute host paths. The root string itself is replaced, so a gate that
# searches for /var/folders or /Volumes finds nothing. A repo-relative path
# (src/tmp/file.py, ./notes/var/folders/readme) stays: the slash is preceded
# by a word, a dot, or a hyphen. `../var/folders` and file:///private/tmp
# are host paths and are replaced. /Volumes is replaced even after a letter
# so /System/Volumes and a truncated n/Volumes do not keep the root.
_HOST_ABS = re.compile(
    r"(?:(?<![A-Za-z0-9_.-])|(?<=\.\.)|(?<=\\n))"
    r"(?:/private/var|/var/folders|/opt/homebrew|/usr/local|/private/tmp|/System/Volumes|/Volumes|/tmp)"
    r"(?:/[^\s\"'`<>|]*)?"
    r"|/Volumes(?:/[^\s\"'`<>|]*)?"
)
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
    ("truncated_secret", _TRUNC_KEY),
    ("host_abs_path", _HOST_ABS),
)


def _home_sub(match: re.Match) -> str:
    kind = "home" if match.group(1).lower() == "home" else "Users"
    return f"/{kind}/<user>"


def _home_enc_sub(match: re.Match) -> str:
    kind = "home" if match.group(1).lower() == "home" else "Users"
    return f"%2F{kind}%2F<user>"


# (pattern, replacement). Replacement is a string (expanded) or a callable.
# Order matches the single-string redactor and stays idempotent.
_REDACT_STEPS = (
    (_PEM, "<redacted-private-key>"),
    (_CONN_SPLIT, r"\1://<redacted>"),
    (_CONN, r"\1://<redacted>"),
    (_USERINFO, r"\1<redacted>@"),
    (_BEARER, r"\1 <redacted>"),
    (_TRUNC_KEY, "<redacted-key>"),
    (_KEY, "<redacted-key>"),
    (_OP, "<redacted-op>"),
    (_ENV, lambda m: m.group("head") + "<redacted>"),
    (_GHP_PREFIX, "<redacted-key>"),
    (_GITHUB_PAT_PREFIX, "<redacted-key>"),
    (_AKIA_PREFIX, "<redacted-key>"),
    # A bare sk- prefix, not the letters inside task-, risk-, ask-, disk-, or mask-.
    (_SK_PREFIX, "<redacted-key>"),
    (_PRIVATE_WORD, "<redacted-private-key>"),
    (_EMAIL, "<email>"),
    # Host roots before the claude-tmp collapse, so /tmp/... becomes <abs>/…
    # and does not keep the username that was encoded inside it.
    (_HOST_ABS, "<abs>/\u2026"),
    (_TMP_CLAUDE, "<tmp>"),
    (_USERS_PATH_ENC, "<tmp>"),
    (_HOME, _home_sub),
    (_HOME_ENC, _home_enc_sub),
    (_USERNAME, "<user>"),
    (_HOST, "<host>"),
    # Username@hostname becomes <user>@<host> only after both replacements.
    (_EMAIL, "<email>"),
)


def _apply_step(pattern: re.Pattern, repl, text: str, owners: list[int]) -> tuple[str, list[int]]:
    """Replace matches. A span that crosses parts is written into the part where it starts."""
    if not text:
        return text, owners
    out: list[str] = []
    out_owners: list[int] = []
    last = 0
    for match in pattern.finditer(text):
        start, end = match.start(), match.end()
        if end <= last:
            continue
        out.append(text[last:start])
        out_owners.extend(owners[last:start])
        replacement = repl(match) if callable(repl) else match.expand(repl)
        if start < len(owners):
            owner = owners[start]
        elif owners:
            owner = owners[-1]
        else:
            owner = 0
        out.append(replacement)
        out_owners.extend([owner] * len(replacement))
        last = end
    out.append(text[last:])
    out_owners.extend(owners[last:])
    return "".join(out), out_owners


def _redact_owned(text: str, owners: list[int]) -> tuple[str, list[int]]:
    """Run every redaction step. owners[i] is the part that owns text[i]."""
    if "\x00" in text:
        kept = [(char, owner) for char, owner in zip(text, owners) if char != "\x00"]
        text = "".join(char for char, _owner in kept)
        owners = [owner for _char, owner in kept]
    if len(owners) != len(text):
        owners = [owners[0] if owners else 0] * len(text)
    for pattern, repl in _REDACT_STEPS:
        text, owners = _apply_step(pattern, repl, text, owners)
        if len(owners) != len(text):
            owners = [owners[0] if owners else 0] * len(text)
    return text, owners


def redact_text(text: str) -> str:
    """Replace secret-shaped substrings. Idempotent on its own output."""
    if not text:
        return text
    redacted, _owners = _redact_owned(text, [0] * len(text))
    return redacted


def redact_joined_parts(parts: list[str]) -> list[str]:
    """Redact the concatenation of parts, then map replacements back.

    A secret split across two adjacent strings is one match on the join.
    The replacement is stored in the part where the match starts, and the
    overlapped characters are removed from the later parts.
    """
    if not parts:
        return []
    owners: list[int] = []
    chunks: list[str] = []
    for index, part in enumerate(parts):
        piece = part or ""
        chunks.append(piece)
        owners.extend([index] * len(piece))
    redacted, new_owners = _redact_owned("".join(chunks), owners)
    rebuilt = [[] for _ in parts]
    for char, owner in zip(redacted, new_owners):
        if 0 <= owner < len(rebuilt):
            rebuilt[owner].append(char)
    return ["".join(buf) for buf in rebuilt]


def message_tool_parts(record: Any) -> list[tuple[dict, str]]:
    """Message content and tool-call arguments, in episode order.

    These are the strings a secret can be split across. The pair is the
    mutable slot the offset map writes back to.
    """
    slots: list[tuple[dict, str]] = []
    if not isinstance(record, dict):
        return slots
    messages = record.get("messages")
    if not isinstance(messages, list):
        return slots
    for message in messages:
        if not isinstance(message, dict):
            continue
        if isinstance(message.get("content"), str):
            slots.append((message, "content"))
        for call in message.get("tool_calls") or []:
            if not isinstance(call, dict):
                continue
            fn = call.get("function")
            if isinstance(fn, dict) and isinstance(fn.get("arguments"), str):
                slots.append((fn, "arguments"))
    return slots


def joined_message_tool_text(record: Any) -> str:
    """Concatenation of message and tool strings. No separator."""
    return "".join(container[key] for container, key in message_tool_parts(record))


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


def residual_episode(obj: Any) -> list[str]:
    """Per-string residuals plus residuals on the joined message/tool text.

    A secret split across adjacent strings matches only the concatenation.
    Any hit here is fail-closed: the caller drops the window.
    """
    hits = residual_object(obj)
    joined = joined_message_tool_text(obj)
    for name in residual_names(joined):
        if name not in hits:
            hits.append(name)
    return hits


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
        return residual_episode(obj)
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
    slots = message_tool_parts(cleaned)
    redacted_parts = redact_joined_parts([container[key] for container, key in slots])
    for (container, key), text in zip(slots, redacted_parts):
        container[key] = text
    cleaned = _map_strings(cleaned, lambda s: redact_text(s) if isinstance(s, str) else s)
    hits = residual_episode(cleaned)
    return cleaned, hits


def drop_if_residual(record: dict) -> tuple[dict | None, list[str]]:
    """Drop a record that still matches, including a secret split across strings."""
    hits = residual_episode(record)
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
