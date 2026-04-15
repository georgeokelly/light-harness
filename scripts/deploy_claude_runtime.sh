#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOK_MANIFEST="${ROOT_DIR}/config/hooks/claude.json"
MERGE_HELPER="${ROOT_DIR}/scripts/merge_runtime_config.py"

TARGET=".claude"
SETTINGS_SCOPE="local"
INCLUDE_HOOKS=1
DRY_RUN=0

usage() {
  echo "Usage: bash scripts/deploy_claude_runtime.sh [--target <path>] [--scope local|project] [--no-hooks] [--dry-run]"
}

resolve_target_dir() {
  if [[ "${TARGET}" = /* ]]; then
    TARGET_DIR="${TARGET}"
  else
    TARGET_DIR="${ROOT_DIR}/${TARGET}"
  fi
}

settings_file_name() {
  if [[ "${SETTINGS_SCOPE}" = "project" ]]; then
    printf 'settings.json'
  else
    printf 'settings.local.json'
  fi
}

merge_hooks() {
  local dst_settings="${TARGET_DIR}/$(settings_file_name)"

  if [[ ${INCLUDE_HOOKS} -eq 0 ]]; then
    return 0
  fi
  if [[ ! -f "${HOOK_MANIFEST}" ]]; then
    echo "[warn] hook manifest not found: ${HOOK_MANIFEST}"
    return 0
  fi
  if [[ ! -f "${MERGE_HELPER}" ]]; then
    echo "[error] merge helper not found: ${MERGE_HELPER}"
    exit 1
  fi

  if [[ ${DRY_RUN} -eq 1 ]]; then
    python3 "${MERGE_HELPER}" --manifest "${HOOK_MANIFEST}" --target "${dst_settings}" --dry-run
  else
    python3 "${MERGE_HELPER}" --manifest "${HOOK_MANIFEST}" --target "${dst_settings}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 ]]; then
        echo "[error] --target requires a path"
        usage
        exit 1
      fi
      TARGET="$2"
      shift 2
      ;;
    --scope)
      if [[ $# -lt 2 ]]; then
        echo "[error] --scope requires a value"
        usage
        exit 1
      fi
      SETTINGS_SCOPE="$2"
      if [[ "${SETTINGS_SCOPE}" != "local" && "${SETTINGS_SCOPE}" != "project" ]]; then
        echo "[error] --scope must be one of: local, project"
        exit 1
      fi
      shift 2
      ;;
    --no-hooks)
      INCLUDE_HOOKS=0
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[error] unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

resolve_target_dir
merge_hooks

echo "[done] claude runtime deployment complete"
