#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RULE_SOURCE_DIR="${ROOT_DIR}/content/rules"
HOOK_MANIFEST="${ROOT_DIR}/config/hooks/cursor.json"
MERGE_HELPER="${ROOT_DIR}/scripts/merge_runtime_config.py"

TARGET=".cursor"
INCLUDE_HOOKS=1
DRY_RUN=0

usage() {
  echo "Usage: bash scripts/deploy_cursor_runtime.sh [--target <path>] [--no-hooks] [--dry-run]"
}

resolve_target_dir() {
  if [[ "${TARGET}" = /* ]]; then
    TARGET_DIR="${TARGET}"
  else
    TARGET_DIR="${ROOT_DIR}/${TARGET}"
  fi
}

require_rule_files() {
  if [[ ! -d "${RULE_SOURCE_DIR}" ]]; then
    echo "[error] rule source directory missing: ${RULE_SOURCE_DIR}"
    exit 1
  fi

  shopt -s nullglob
  RULE_FILES=("${RULE_SOURCE_DIR}"/*.md)
  shopt -u nullglob

  if [[ ${#RULE_FILES[@]} -eq 0 ]]; then
    echo "[error] no rule files found in: ${RULE_SOURCE_DIR}"
    exit 1
  fi
}

render_rules() {
  local src=""
  local src_name=""
  local base_name=""
  local dst=""

  for src in "${RULE_FILES[@]}"; do
    src_name="$(basename "${src}")"
    base_name="${src_name%.md}"
    dst="${TARGET_DIR}/rules/${base_name}.mdc"

    if [[ ${DRY_RUN} -eq 1 ]]; then
      echo "[dry-run] write ${dst}"
      continue
    fi

    mkdir -p "$(dirname "${dst}")"
    {
      printf -- '---\n'
      printf 'description: deployed from content/rules/%s\n' "${src_name}"
      printf 'alwaysApply: true\n'
      printf -- '---\n\n'
      cat "${src}"
    } > "${dst}"
    echo "[ok] wrote ${dst}"
  done
}

merge_hooks() {
  local dst_hooks="${TARGET_DIR}/hooks.json"

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
    python3 "${MERGE_HELPER}" --manifest "${HOOK_MANIFEST}" --target "${dst_hooks}" --dry-run
  else
    python3 "${MERGE_HELPER}" --manifest "${HOOK_MANIFEST}" --target "${dst_hooks}"
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
require_rule_files
render_rules
merge_hooks

echo "[done] cursor runtime deployment complete"
