#!/usr/bin/env python3
"""Remove light-harness managed runtime settings from a target workspace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]
CURSOR_RULE_FILES = (
    "15-light-harness.mdc",
    "16-action-risk-matrix.mdc",
    "17-verification-levels.mdc",
)


def color_tag(level: str) -> str:
    """Return colored tag text when stdout is a tty."""
    if not sys.stdout.isatty():
        return f"[{level}]"
    colors = {
        "ok": "\033[32m",
        "done": "\033[32m",
        "info": "\033[34m",
        "skip": "\033[38;5;208m",
        "warn": "\033[31m",
        "error": "\033[31m",
    }
    color = colors.get(level)
    if not color:
        return f"[{level}]"
    return f"{color}[{level}]\033[0m"


def log(level: str, message: str) -> None:
    """Print a tagged log line."""
    print(f"{color_tag(level)} {message}")


def read_json(path: Path) -> JsonDict:
    """Read a JSON object from disk; return empty object when missing."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def write_json(path: Path, data: JsonDict) -> None:
    """Write a JSON object with stable formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_managed_command(entry: Any) -> bool:
    """Return True when a hook command belongs to light-harness."""
    if not isinstance(entry, dict):
        return False
    command = entry.get("command")
    if not isinstance(command, str):
        return False
    return "light_harness_hook.py" in command and "--event" in command


def strip_managed_hooks(data: JsonDict) -> tuple[JsonDict, bool]:
    """Remove harness-managed hook handlers from one hooks object."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return data, False

    changed = False
    new_hooks: JsonDict = {}

    for event, entries in hooks.items():
        if not isinstance(entries, list):
            new_hooks[event] = entries
            continue

        kept_entries: list[Any] = []
        for entry in entries:
            if not isinstance(entry, dict):
                kept_entries.append(entry)
                continue

            nested_hooks = entry.get("hooks")
            if isinstance(nested_hooks, list):
                kept_nested = [hook for hook in nested_hooks if not is_managed_command(hook)]
                if len(kept_nested) != len(nested_hooks):
                    changed = True
                if kept_nested:
                    new_entry = dict(entry)
                    new_entry["hooks"] = kept_nested
                    kept_entries.append(new_entry)
                continue

            if is_managed_command(entry):
                changed = True
                continue

            kept_entries.append(entry)

        if kept_entries:
            new_hooks[event] = kept_entries
        else:
            if event in hooks:
                changed = True

    result = dict(data)
    if new_hooks:
        result["hooks"] = new_hooks
    elif "hooks" in result:
        result.pop("hooks", None)
        changed = True
    return result, changed


def uninstall_hooks_file(path: Path, dry_run: bool) -> None:
    """Remove managed hook handlers from one runtime JSON config file."""
    if not path.exists():
        log("skip", f"hooks config not found: {path}")
        return

    try:
        config = read_json(path)
    except Exception as exc:
        log("error", f"failed to read hooks config {path}: {exc}")
        return

    merged, changed = strip_managed_hooks(config)
    if not changed:
        log("skip", f"no managed hooks to remove in {path}")
        return

    if dry_run:
        log("info", f"dry-run: would remove managed hooks from {path}")
        return

    write_json(path, merged)
    log("ok", f"removed managed hooks from {path}")


def remove_cursor_rules(cursor_target: Path, dry_run: bool) -> None:
    """Remove harness-generated Cursor rule files."""
    rules_dir = cursor_target / "rules"
    for name in CURSOR_RULE_FILES:
        path = rules_dir / name
        if not path.exists():
            log("skip", f"cursor rule not found: {path}")
            continue
        if dry_run:
            log("info", f"dry-run: would remove {path}")
            continue
        path.unlink()
        log("ok", f"removed {path}")


def unset_codex_hooks_flag(codex_target: Path, dry_run: bool) -> None:
    """Best-effort removal of `codex_hooks` feature flag."""
    path = codex_target / "config.toml"
    if not path.exists():
        log("skip", f"codex config not found: {path}")
        return

    lines = path.read_text(encoding="utf-8").splitlines()
    result: list[str] = []
    in_features = False
    changed = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_features = stripped == "[features]"
            result.append(line)
            continue
        if in_features and stripped.startswith("codex_hooks") and "=" in stripped:
            changed = True
            continue
        result.append(line)

    if not changed:
        log("skip", f"codex_hooks flag not found in {path}")
        return

    if dry_run:
        log("info", f"dry-run: would remove codex_hooks flag from {path}")
        return

    path.write_text("\n".join(result).rstrip() + "\n", encoding="utf-8")
    log("ok", f"removed codex_hooks flag from {path}")


def remove_mode_file(target_root: Path, dry_run: bool) -> None:
    """Remove pre-tool-use mode override file."""
    path = target_root / ".agent-memory" / "tmp" / "pretooluse-mode"
    if not path.exists():
        log("skip", f"mode file not found: {path}")
        return
    if dry_run:
        log("info", f"dry-run: would remove mode file {path}")
        return
    path.unlink()
    log("ok", f"removed mode file {path}")


def purge_state(target_root: Path, dry_run: bool) -> None:
    """Remove generated local-state files under records/current."""
    state_dir = target_root / ".agent-memory" / "records" / "current"
    files = (
        "preflight.md",
        "record.md",
        "approvals.md",
        "hook.log",
        "scope-violations.log",
        "_code_change.flag",
    )
    for name in files:
        path = state_dir / name
        if not path.exists():
            log("skip", f"state file not found: {path}")
            continue
        if dry_run:
            log("info", f"dry-run: would remove {path}")
            continue
        path.unlink()
        log("ok", f"removed {path}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-root", required=True, help="target workspace root")
    parser.add_argument("--cursor-target", help="cursor runtime directory (.cursor)")
    parser.add_argument("--codex-target", help="codex runtime directory (.codex)")
    parser.add_argument("--claude-target", help="claude runtime directory (.claude)")
    parser.add_argument(
        "--claude-scope",
        choices=("local", "project", "both"),
        default="both",
        help="which Claude settings file to clean",
    )
    parser.add_argument("--no-cursor", action="store_true", help="skip Cursor runtime cleanup")
    parser.add_argument("--no-codex", action="store_true", help="skip Codex runtime cleanup")
    parser.add_argument("--no-claude", action="store_true", help="skip Claude runtime cleanup")
    parser.add_argument(
        "--purge-state",
        action="store_true",
        help="also remove local state files under .agent-memory/records/current",
    )
    parser.add_argument("--dry-run", action="store_true", help="print actions without writing")
    return parser.parse_args()


def resolve_path(value: str | None, default_path: Path) -> Path:
    """Resolve one optional path argument."""
    if not value:
        return default_path
    path = Path(value)
    if path.is_absolute():
        return path.resolve()
    return path.resolve()


def main() -> int:
    """Run runtime uninstall actions."""
    args = parse_args()
    target_root = Path(args.target_root).resolve()

    cursor_target = resolve_path(args.cursor_target, target_root / ".cursor")
    codex_target = resolve_path(args.codex_target, target_root / ".codex")
    claude_target = resolve_path(args.claude_target, target_root / ".claude")

    log("info", f"target workspace root: {target_root}")
    if args.no_cursor and args.no_codex and args.no_claude:
        log("warn", "all runtime cleanups are disabled; only mode/state cleanup will run")

    if not args.no_cursor:
        uninstall_hooks_file(cursor_target / "hooks.json", dry_run=args.dry_run)
        remove_cursor_rules(cursor_target, dry_run=args.dry_run)

    if not args.no_codex:
        uninstall_hooks_file(codex_target / "hooks.json", dry_run=args.dry_run)
        unset_codex_hooks_flag(codex_target, dry_run=args.dry_run)

    if not args.no_claude:
        if args.claude_scope in ("local", "both"):
            uninstall_hooks_file(claude_target / "settings.local.json", dry_run=args.dry_run)
        if args.claude_scope in ("project", "both"):
            uninstall_hooks_file(claude_target / "settings.json", dry_run=args.dry_run)

    remove_mode_file(target_root, dry_run=args.dry_run)
    if args.purge_state:
        purge_state(target_root, dry_run=args.dry_run)

    log("done", "light-harness runtime uninstall complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
