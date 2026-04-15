#!/usr/bin/env python3
"""Merge harness-managed runtime config without clobbering user settings."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

JsonDict = dict[str, Any]


def read_json(path: Path) -> JsonDict:
    """Read a JSON object from disk.

    Args:
        path: JSON file path.

    Returns:
        Parsed JSON object, or an empty object when the file does not exist.

    Raises:
        ValueError: If the file exists but does not contain a JSON object.
    """

    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object in {path}")
    return data


def write_json(path: Path, data: JsonDict) -> None:
    """Write a JSON object with stable pretty formatting.

    Args:
        path: Output file path.
        data: JSON object to serialize.

    Returns:
        None.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_manifest(path: Path) -> JsonDict:
    """Load and validate a runtime manifest.

    Args:
        path: Manifest file path.

    Returns:
        Parsed manifest object.

    Raises:
        ValueError: If required manifest fields are missing or malformed.
    """

    manifest = read_json(path)
    required_keys = ("runtime", "mergeMode", "managedCommands", "config")
    missing = [key for key in required_keys if key not in manifest]
    if missing:
        raise ValueError(f"manifest missing required keys: {', '.join(missing)}")

    if not isinstance(manifest["managedCommands"], list):
        raise ValueError("manifest field `managedCommands` must be a list")
    if not isinstance(manifest["config"], dict):
        raise ValueError("manifest field `config` must be an object")
    return manifest


def event_names(existing_hooks: JsonDict, template_hooks: JsonDict) -> list[str]:
    """Return deterministic event order for merge operations.

    Args:
        existing_hooks: Hooks already present in the target file.
        template_hooks: Hooks supplied by the harness manifest.

    Returns:
        Event names with existing order preserved and new template events appended.
    """

    names = list(existing_hooks.keys())
    for name in template_hooks.keys():
        if name not in existing_hooks:
            names.append(name)
    return names


def is_managed_command(entry: Any, managed_commands: set[str]) -> bool:
    """Check whether a hook handler belongs to light-harness.

    Args:
        entry: Hook handler candidate.
        managed_commands: Commands owned by the harness manifest.

    Returns:
        True when the handler command is harness-managed, else False.
    """

    return isinstance(entry, dict) and entry.get("command") in managed_commands


def strip_managed_entries(entries: list[Any], managed_commands: set[str]) -> list[Any]:
    """Remove harness-managed handlers while keeping user-owned content.

    Args:
        entries: Event entries from the existing config.
        managed_commands: Commands owned by the harness manifest.

    Returns:
        Event entries with managed handlers removed.
    """

    cleaned: list[Any] = []
    for entry in entries:
        if not isinstance(entry, dict):
            cleaned.append(entry)
            continue

        nested_hooks = entry.get("hooks")
        if isinstance(nested_hooks, list):
            kept_hooks = [
                hook for hook in nested_hooks if not is_managed_command(hook, managed_commands)
            ]
            if kept_hooks:
                new_entry = copy.deepcopy(entry)
                new_entry["hooks"] = kept_hooks
                cleaned.append(new_entry)
            continue

        if not is_managed_command(entry, managed_commands):
            cleaned.append(copy.deepcopy(entry))
    return cleaned


def merge_hook_objects(
    existing_hooks: JsonDict, template_hooks: JsonDict, managed_commands: set[str]
) -> JsonDict:
    """Merge hook objects while replacing only harness-managed handlers.

    Args:
        existing_hooks: Existing `hooks` object from the target config.
        template_hooks: Harness-managed `hooks` object from the manifest.
        managed_commands: Commands owned by the harness manifest.

    Returns:
        A merged hooks object.
    """

    result: JsonDict = {}
    for name in event_names(existing_hooks, template_hooks):
        existing_entries = existing_hooks.get(name, [])
        template_entries = template_hooks.get(name, [])

        if not isinstance(existing_entries, list):
            existing_entries = []
        if not isinstance(template_entries, list):
            raise ValueError(f"template hooks for event `{name}` must be a list")

        cleaned = strip_managed_entries(existing_entries, managed_commands)
        merged_entries = cleaned + copy.deepcopy(template_entries)
        if merged_entries:
            result[name] = merged_entries
    return result


def merge_runtime_config(manifest: JsonDict, target: JsonDict) -> JsonDict:
    """Merge one runtime config according to manifest rules.

    Args:
        manifest: Runtime manifest with merge mode and managed hooks.
        target: Existing target config object.

    Returns:
        Merged config object.

    Raises:
        ValueError: If the merge mode is unsupported.
    """

    merge_mode = manifest["mergeMode"]
    managed_commands = {str(command) for command in manifest["managedCommands"]}
    template_config = manifest["config"]

    result = copy.deepcopy(target)
    existing_hooks = result.get("hooks", {})
    template_hooks = template_config.get("hooks", {})

    if existing_hooks and not isinstance(existing_hooks, dict):
        raise ValueError("existing target field `hooks` must be an object")
    if template_hooks and not isinstance(template_hooks, dict):
        raise ValueError("template field `config.hooks` must be an object")

    if merge_mode == "hooks_file":
        for key, value in template_config.items():
            if key != "hooks":
                result[key] = copy.deepcopy(value)
        result["hooks"] = merge_hook_objects(existing_hooks, template_hooks, managed_commands)
        return result

    if merge_mode == "settings_hooks_object":
        result["hooks"] = merge_hook_objects(existing_hooks, template_hooks, managed_commands)
        return result

    raise ValueError(f"unsupported merge mode: {merge_mode}")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed CLI arguments.
    """

    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, help="runtime manifest path")
    parser.add_argument("--target", required=True, help="runtime config target path")
    parser.add_argument("--dry-run", action="store_true", help="print summary without writing")
    return parser.parse_args()


def main() -> int:
    """Run the merge helper CLI.

    Returns:
        Process exit code.
    """

    args = parse_args()
    manifest_path = Path(args.manifest)
    target_path = Path(args.target)

    manifest = load_manifest(manifest_path)
    target = read_json(target_path)
    merged = merge_runtime_config(manifest, target)

    if args.dry_run:
        print(
            f"[dry-run] {manifest['runtime']} merge into {target_path} "
            f"({len(manifest['managedCommands'])} managed commands)"
        )
        return 0

    write_json(target_path, merged)
    print(
        f"[ok] wrote {target_path} "
        f"({len(manifest['managedCommands'])} managed commands)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
