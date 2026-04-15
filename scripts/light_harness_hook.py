#!/usr/bin/env python3
"""Light harness hook backstop.

This script is intentionally conservative:
- Strict events may block execution with non-zero exit.
- Non-strict events emit warnings and keep flow moving.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BLOCK_EXIT_CODE = 2

REQUIRED_PREFLIGHT_HEADINGS = [
    "Goal",
    "Constraints",
    "Forbidden",
    "Out of scope",
    "Success criteria",
    "Planned scope",
    "Verification level",
]

RECORD_REQUIRED_HEADINGS_V1_PLUS = [
    "Verification performed",
    "Unverified items",
    "User involvement",
]


def workspace_root() -> Path:
    # scripts/light_harness_hook.py -> repo root is parents[1]
    return Path(__file__).resolve().parents[1]


ROOT = workspace_root()
STATE_DIR = ROOT / ".agent-memory" / "records" / "current"
TMP_DIR = ROOT / ".agent-memory" / "tmp"
PREFLIGHT_FILE = STATE_DIR / "preflight.md"
RECORD_FILE = STATE_DIR / "record.md"
APPROVAL_FILE = STATE_DIR / "approvals.md"
HOOK_LOG = STATE_DIR / "hook.log"
SCOPE_VIOLATION_LOG = STATE_DIR / "scope-violations.log"
CODE_CHANGE_FLAG = STATE_DIR / "_code_change.flag"
PRETOOLUSE_MODE_FILE = TMP_DIR / "pretooluse-mode"

CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".swift",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cc",
    ".cxx",
    ".cs",
    ".rb",
    ".php",
    ".sh",
    ".bash",
    ".zsh",
    ".sql",
}

NON_CODE_EXTENSIONS = {
    ".md",
    ".drawio",
    ".html",
    ".htm",
}

SHELL_PUNCTUATION = "|&;(){}"
SHELL_SEPARATORS = {";", "&&", "||", "|", "(", ")", "{", "}"}
SHELL_WRAPPER_COMMANDS = {"env", "sudo", "command", "exec", "nohup", "time"}
SHELL_COMMAND_EXECUTORS = {"bash", "sh", "zsh", "dash", "ksh", "fish"}
SHELL_COMMAND_FLAGS = {"-c", "-lc", "-ic", "--command"}
MAX_COMMAND_PARSE_DEPTH = 6


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def ensure_tmp_dir() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)


def append_log(path: Path, message: str) -> None:
    ensure_state_dir()
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{utc_now()} {message}\n")


def info(message: str) -> None:
    print(f"[LIGHT-HARNESS] {message}")
    append_log(HOOK_LOG, f"INFO {message}")


def warn(message: str) -> None:
    print(f"[LIGHT-HARNESS WARN] {message}")
    append_log(HOOK_LOG, f"WARN {message}")


def block(message: str) -> int:
    print(f"[LIGHT-HARNESS BLOCK] {message}")
    append_log(HOOK_LOG, f"BLOCK {message}")
    return BLOCK_EXIT_CODE


def read_stdin() -> str:
    try:
        return sys.stdin.read()
    except Exception:
        return ""


def parse_payload(raw: str) -> dict[str, Any]:
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return {"payload": data}
    except Exception as exc:
        return {"raw": raw, "_parse_error": str(exc)}


def extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(filter(None, (extract_text(v) for v in value)))
    if isinstance(value, dict):
        parts: list[str] = []
        for key in (
            "prompt",
            "input",
            "text",
            "message",
            "userPrompt",
            "user_prompt",
            "query",
            "command",
            "cmd",
            "shell_command",
            "filePath",
            "file_path",
            "path",
            "relative_path",
            "shellCommand",
            "raw",
        ):
            v = value.get(key)
            if isinstance(v, str):
                parts.append(v)
        for v in value.values():
            if isinstance(v, (dict, list)):
                nested = extract_text(v)
                if nested:
                    parts.append(nested)
        return "\n".join(parts)
    return ""


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def extract_path_value(value: Any) -> str:
    if isinstance(value, dict):
        for key in (
            "path",
            "filePath",
            "file_path",
            "relativePath",
            "relative_path",
            "target",
        ):
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for nested in value.values():
            candidate = extract_path_value(nested)
            if candidate:
                return candidate
    elif isinstance(value, list):
        for nested in value:
            candidate = extract_path_value(nested)
            if candidate:
                return candidate
    return ""


def missing_headings(markdown: str, headings: list[str]) -> list[str]:
    missing: list[str] = []
    for heading in headings:
        pattern = re.compile(
            rf"(^|\n)\s*#+\s*{re.escape(heading)}\s*$", re.IGNORECASE | re.MULTILINE
        )
        if not pattern.search(markdown):
            missing.append(heading)
    return missing


def preflight_status(markdown: str) -> str:
    match = re.search(
        r"^\s*Status:\s*`?([a-zA-Z\-]+)`?\s*$", markdown, re.IGNORECASE | re.MULTILINE
    )
    if not match:
        return ""
    return match.group(1).strip().lower()


def parse_verification_level(markdown: str) -> str:
    section = extract_section(markdown, r"Verification level")
    if section:
        match = re.search(
            r"^\s*(?:-\s*)?`?(V[0-3])`?\s*(?:<!--.*-->)?\s*$",
            section,
            re.IGNORECASE | re.MULTILINE,
        )
        if match:
            return match.group(1).upper()

    match = re.search(
        r"^\s*Verification level:\s*`?(V[0-3])`?\s*$",
        markdown,
        re.IGNORECASE | re.MULTILINE,
    )
    if match:
        return match.group(1).upper()
    return "V1"


def parse_planned_scope(markdown: str) -> list[str]:
    section = re.search(
        r"(?is)^##\s*Planned scope\s*$([\s\S]*?)(?:^\s*##\s+|\Z)",
        markdown,
        re.MULTILINE,
    )
    if not section:
        return []
    block = section.group(1)
    items: list[str] = []
    for line in block.splitlines():
        line = line.strip()
        if not line.startswith("- "):
            continue
        item = line[2:].strip().strip("`")
        if item:
            items.append(item)
    return items


def extract_section(markdown: str, heading_pattern: str) -> str:
    section = re.search(
        rf"(?is)^##\s*{heading_pattern}\s*$([\s\S]*?)(?:^\s*##\s+|\Z)",
        markdown,
        re.MULTILINE,
    )
    if not section:
        return ""
    return section.group(1).strip()


def is_code_file(path_value: str) -> bool:
    suffix = Path(path_value).suffix.lower()
    if not suffix:
        return False
    if suffix in NON_CODE_EXTENSIONS:
        return False
    return suffix in CODE_EXTENSIONS


def mark_code_change(path_value: str) -> None:
    ensure_state_dir()
    entry = f"{utc_now()} {path_value}\n"
    with CODE_CHANGE_FLAG.open("a", encoding="utf-8") as f:
        f.write(entry)


def read_pretooluse_mode() -> str:
    raw = read_text(PRETOOLUSE_MODE_FILE).strip().lower()
    if not raw:
        return "normal"
    if raw in {"normal", "sandbox"}:
        return raw
    warn(
        f"Unknown pre-tool-use mode `{raw}` in {PRETOOLUSE_MODE_FILE}; "
        "falling back to `normal`."
    )
    return "normal"


def token_is_rm(token: str) -> bool:
    stripped = token.strip()
    if not stripped:
        return False
    return Path(stripped).name == "rm"


def split_shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=SHELL_PUNCTUATION)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def is_assignment_token(token: str) -> bool:
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*=.*$", token))


def assignment_sets_rm(token: str) -> bool:
    if not is_assignment_token(token):
        return False
    _, value = token.split("=", 1)
    cleaned = value.strip().strip("'\"")
    return token_is_rm(cleaned)


def extract_inline_commands(command: str) -> list[str]:
    snippets: list[str] = []
    for match in re.finditer(r"\$\(([^()]+)\)", command):
        snippet = match.group(1).strip()
        if snippet:
            snippets.append(snippet)
    for match in re.finditer(r"`([^`]+)`", command):
        snippet = match.group(1).strip()
        if snippet:
            snippets.append(snippet)
    return snippets


def command_contains_rm(command: str, depth: int = 0) -> bool:
    if depth > MAX_COMMAND_PARSE_DEPTH:
        # Fail closed when parsing depth is exceeded.
        return True
    text = command.strip()
    if not text:
        return False
    if "rm" not in text:
        return False

    for snippet in extract_inline_commands(text):
        if command_contains_rm(snippet, depth + 1):
            return True

    try:
        tokens = split_shell_tokens(text)
    except ValueError:
        # Fall back to conservative split on common separators.
        tokens = [
            piece
            for piece in re.split(r"(\|\||&&|[;|(){}])|\s+", text)
            if piece and not piece.isspace()
        ]

    i = 0
    command_start = True
    while i < len(tokens):
        token = tokens[i].strip()
        if not token:
            i += 1
            continue
        if token in SHELL_SEPARATORS:
            command_start = True
            i += 1
            continue
        if not command_start:
            i += 1
            continue

        while i < len(tokens) and is_assignment_token(tokens[i]):
            if assignment_sets_rm(tokens[i]):
                return True
            i += 1

        if i >= len(tokens):
            break

        token = tokens[i].strip()
        if not token:
            i += 1
            continue
        if token in SHELL_SEPARATORS:
            command_start = True
            i += 1
            continue

        while token in SHELL_WRAPPER_COMMANDS:
            i += 1
            while i < len(tokens):
                wrapper_arg = tokens[i].strip()
                if wrapper_arg in SHELL_SEPARATORS:
                    break
                if wrapper_arg.startswith("-"):
                    i += 1
                    continue
                if is_assignment_token(wrapper_arg):
                    if assignment_sets_rm(wrapper_arg):
                        return True
                    i += 1
                    continue
                break
            if i >= len(tokens):
                return False
            token = tokens[i].strip()
        if token in SHELL_SEPARATORS:
            command_start = True
            continue

        if token_is_rm(token):
            return True

        if token in SHELL_COMMAND_EXECUTORS:
            j = i + 1
            while j < len(tokens) and tokens[j] not in SHELL_SEPARATORS:
                shell_arg = tokens[j]
                if shell_arg in SHELL_COMMAND_FLAGS and j + 1 < len(tokens):
                    if command_contains_rm(tokens[j + 1], depth + 1):
                        return True
                    break
                j += 1

        if token == "xargs":
            j = i + 1
            while j < len(tokens) and tokens[j] not in SHELL_SEPARATORS:
                xarg = tokens[j]
                if xarg.startswith("-"):
                    j += 1
                    continue
                if is_assignment_token(xarg):
                    if assignment_sets_rm(xarg):
                        return True
                    j += 1
                    continue
                if token_is_rm(xarg):
                    return True
                if xarg in SHELL_COMMAND_EXECUTORS:
                    k = j + 1
                    while k < len(tokens) and tokens[k] not in SHELL_SEPARATORS:
                        if tokens[k] in SHELL_COMMAND_FLAGS and k + 1 < len(tokens):
                            if command_contains_rm(tokens[k + 1], depth + 1):
                                return True
                            break
                        k += 1
                break

        command_start = False
        i += 1

    return False


def has_reasoning_chain(record_markdown: str) -> bool:
    section = extract_section(record_markdown, r"Reasoning chain(?:\s*\(.*\))?")
    if not section:
        return False
    numbered = re.findall(r"^\s*\d+\.\s+\S+", section, re.MULTILINE)
    return len(numbered) >= 3


def normalize_relative_path(path: str) -> str:
    value = path.replace("\\", "/").strip()
    while value.startswith("./"):
        value = value[2:]
    value = value.lstrip("/")
    if not value:
        return ""

    parts: list[str] = []
    for part in value.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            return ""
        parts.append(part)
    return "/".join(parts)


def path_in_scope(path: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    normalized = normalize_relative_path(path)
    if not normalized:
        return False
    for pat in patterns:
        pat_norm = normalize_relative_path(pat)
        if not pat_norm:
            continue
        if any(ch in pat_norm for ch in ("*", "?", "[")):
            if fnmatch.fnmatch(normalized, pat_norm):
                return True
            continue
        prefix = pat_norm.rstrip("/")
        if normalized == prefix or normalized.startswith(prefix + "/"):
            return True
    return False


def classify_risk(command: str) -> str:
    cmd = command.lower().strip()
    if not cmd:
        return "R0"

    r3_patterns = [
        r"\bgit\s+reset\s+--hard\b",
        r"\bgit\s+clean\s+-fd\b",
        r"\bterraform\s+destroy\b",
        r"\bdrop\s+database\b",
        r"\btruncate\s+table\b",
        r"\bgit\s+push\s+--force\b",
        r"\bnpm\s+install\b",
        r"\bpnpm\s+install\b",
        r"\byarn\s+install\b",
        r"\bpip\s+install\b",
        r"\bcargo\s+install\b",
        r"\bcurl\b",
        r"\bwget\b",
    ]
    for pattern in r3_patterns:
        if re.search(pattern, cmd):
            return "R3"

    r2_patterns = [
        r"\bnpm\s+run\s+dev\b",
        r"\bnpm\s+start\b",
        r"\bpnpm\s+dev\b",
        r"\byarn\s+dev\b",
        r"\bdocker\s+compose\s+up\b",
        r"\buvicorn\b",
        r"\bflask\s+run\b",
        r"\bpython\s+.*-m\s+http\.server\b",
        r"\bgo\s+run\b",
        r"\bcargo\s+run\b",
    ]
    for pattern in r2_patterns:
        if re.search(pattern, cmd):
            return "R2"

    return "R1"


def has_approval(risk: str) -> bool:
    text = read_text(APPROVAL_FILE)
    if not text:
        return False
    marker = f"{risk}:approved"
    if marker in text:
        return True
    if risk == "R2" and "R3:approved" in text:
        return True
    return False


def has_implementation_intent(prompt: str) -> bool:
    if not prompt.strip():
        return False
    pattern = re.compile(
        r"("
        r"implement|fix|refactor|write code|edit|modify|change|build|"
        r"add|create|update|upgrade|remove|delete|rename|move|"
        r"configure|setup|set up|apply|patch|go ahead|"
        r"实现|修复|重构|写代码|修改|改动|新增|增加|创建|更新|删除|重命名|移动|"
        r"配置|继续实现|开始实现|开始改|直接改"
        r")",
        re.IGNORECASE,
    )
    return bool(pattern.search(prompt))


def validate_preflight(strict: bool) -> int:
    preflight = read_text(PREFLIGHT_FILE)
    if not preflight:
        message = (
            "Missing preflight: .agent-memory/records/current/preflight.md. "
            "Run `bash scripts/init_local_state.sh` first."
        )
        if strict:
            return block(message)
        warn(message)
        return 0

    missing = missing_headings(preflight, REQUIRED_PREFLIGHT_HEADINGS)
    if missing:
        message = f"Preflight is missing required headings: {', '.join(missing)}"
        if strict:
            return block(message)
        warn(message)
        return 0

    status = preflight_status(preflight)
    if strict and status != "approved":
        if not status:
            return block(
                "Preflight status is missing. Set `Status: approved` before execution."
            )
        return block(
            "Preflight status is not approved. Set `Status: approved` before execution."
        )

    return 0


def on_before_submit_prompt(payload: dict[str, Any], strict: bool) -> int:
    prompt_text = extract_text(payload)
    if not has_implementation_intent(prompt_text):
        info("Prompt appears non-implementation-heavy. Skipping strict preflight gate.")
        return 0
    return validate_preflight(strict=strict)


def on_before_shell_execution(payload: dict[str, Any], strict: bool) -> int:
    mode = read_pretooluse_mode()
    effective_strict = strict and mode != "sandbox"

    parse_error = payload.get("_parse_error")
    if isinstance(parse_error, str) and parse_error:
        message = (
            "Hook payload is not valid JSON; cannot safely evaluate shell risk. "
            "Fix hook payload format before continuing."
        )
        if effective_strict:
            return block(message)
        warn(message)
        return 0

    command = ""
    for key in ("command", "cmd", "shellCommand", "shell_command"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip():
            command = val.strip()
            break
    if not command:
        command = extract_text(payload).strip()
    if not command:
        raw = payload.get("raw")
        if isinstance(raw, str):
            command = raw.strip()
    if not command:
        warn("Could not infer shell command from hook payload; skipping shell risk check.")
        return 0

    if command_contains_rm(command):
        return block(
            "`rm` is forbidden in all modes. Append deletion requests to "
            "`pending-rm.md` instead of running shell removal commands."
        )

    risk = classify_risk(command)
    info(f"Shell command risk classified as {risk} (mode={mode})")

    preflight_result = validate_preflight(strict=effective_strict)
    if preflight_result != 0:
        return preflight_result

    if risk in ("R2", "R3") and not has_approval(risk):
        message = (
            f"Command risk {risk} requires explicit approval marker. "
            "Add `.agent-memory/records/current/approvals.md` with "
            f"`{risk}:approved` (or `R3:approved` for R2/R3)."
        )
        if effective_strict:
            return block(message)
        warn(message)
        return 0

    return 0


def on_after_file_edit(payload: dict[str, Any], strict: bool) -> int:
    _ = strict  # Non-blocking by design for post-edit checks.

    path_value = extract_path_value(payload)
    if not path_value:
        text = extract_text(payload)
        path_value = text.splitlines()[0].strip() if text.strip() else ""

    preflight = read_text(PREFLIGHT_FILE)
    if not preflight:
        warn("No preflight found during afterFileEdit scope check.")
        return 0

    patterns = parse_planned_scope(preflight)
    if not path_value:
        warn("Could not infer edited file path for scope check.")
        return 0

    if not path_in_scope(path_value, patterns):
        msg = (
            f"Edited path outside planned scope: {path_value}. "
            "Update preflight scope or request scope expansion approval."
        )
        warn(msg)
        append_log(SCOPE_VIOLATION_LOG, msg)

    if is_code_file(path_value):
        mark_code_change(path_value)
        info(f"Code change detected: {path_value}")
    return 0


def on_stop(payload: dict[str, Any], strict: bool) -> int:
    _ = payload
    _ = strict

    preflight = read_text(PREFLIGHT_FILE)
    if not preflight:
        warn("Stop check skipped: no preflight found.")
        return 0

    level = parse_verification_level(preflight)
    if level == "V0":
        info("Stop check: V0 selected, strict verification evidence not required.")
        return 0

    record = read_text(RECORD_FILE)
    if not record:
        warn(
            "Record file missing at stop: .agent-memory/records/current/record.md "
            "(run `bash scripts/init_local_state.sh`)."
        )
        return 0

    missing = missing_headings(record, RECORD_REQUIRED_HEADINGS_V1_PLUS)
    if missing:
        warn(f"Record missing verification sections at stop: {', '.join(missing)}")
        return 0

    if CODE_CHANGE_FLAG.exists() and not has_reasoning_chain(record):
        message = (
            "Code changes were detected but record is missing a sufficient "
            "`Reasoning chain` section (at least 3 numbered steps)."
        )
        if strict:
            return block(message)
        warn(message)
        return 0

    info("Stop check passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--event",
        required=True,
        choices=[
            "beforeSubmitPrompt",
            "beforeShellExecution",
            "afterFileEdit",
            "stop",
        ],
    )
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    payload = parse_payload(read_stdin())

    if args.event == "beforeSubmitPrompt":
        return on_before_submit_prompt(payload, strict=args.strict)
    if args.event == "beforeShellExecution":
        return on_before_shell_execution(payload, strict=args.strict)
    if args.event == "afterFileEdit":
        return on_after_file_edit(payload, strict=args.strict)
    if args.event == "stop":
        return on_stop(payload, strict=args.strict)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
