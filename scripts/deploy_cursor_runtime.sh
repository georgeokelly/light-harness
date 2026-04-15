#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RULE_SOURCE_DIR="${ROOT_DIR}/content/rules"
HOOK_MANIFEST="${ROOT_DIR}/config/hooks/cursor.json"
MERGE_HELPER="${ROOT_DIR}/scripts/merge_runtime_config.py"
INIT_SCRIPT="${ROOT_DIR}/scripts/init_local_state.sh"
HOOK_SCRIPT="${ROOT_DIR}/scripts/light_harness_hook.py"

TARGET=".cursor"
INCLUDE_HOOKS=1
INCLUDE_INIT=1
DRY_RUN=0
RED=""
GREEN=""
BLUE=""
ORANGE=""
RESET=""

usage() {
  echo "Usage: bash scripts/deploy_cursor_runtime.sh [--target <path>] [--no-hooks] [--no-init] [--dry-run]"
}

if [[ -t 1 ]]; then
  RED=$'\033[31m'
  GREEN=$'\033[32m'
  BLUE=$'\033[34m'
  ORANGE=$'\033[38;5;208m'
  RESET=$'\033[0m'
fi

print_tag() {
  local level="$1"
  local message="$2"
  local color=""
  case "${level}" in
    error|warn)
      color="${RED}"
      ;;
    ok|done)
      color="${GREEN}"
      ;;
    info)
      color="${BLUE}"
      ;;
    skip)
      color="${ORANGE}"
      ;;
  esac
  if [[ -n "${color}" && -n "${RESET}" ]]; then
    printf '%s[%s]%s %s\n' "${color}" "${level}" "${RESET}" "${message}"
  else
    printf '[%s] %s\n' "${level}" "${message}"
  fi
}

resolve_target_dir() {
  if [[ "${TARGET}" = /* ]]; then
    TARGET_DIR="${TARGET}"
  else
    TARGET_DIR="${ROOT_DIR}/${TARGET}"
  fi
}

resolve_target_workspace_root() {
  TARGET_WORKSPACE_ROOT="$(dirname "${TARGET_DIR}")"
}

require_rule_files() {
  if [[ ! -d "${RULE_SOURCE_DIR}" ]]; then
    print_tag "error" "rule source directory missing: ${RULE_SOURCE_DIR}"
    exit 1
  fi

  shopt -s nullglob
  RULE_FILES=("${RULE_SOURCE_DIR}"/*.md)
  shopt -u nullglob

  if [[ ${#RULE_FILES[@]} -eq 0 ]]; then
    print_tag "error" "no rule files found in: ${RULE_SOURCE_DIR}"
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
      print_tag "info" "dry-run: write ${dst}"
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
    print_tag "ok" "wrote ${dst}"
  done
}

ensure_local_state() {
  if [[ ${INCLUDE_INIT} -eq 0 ]]; then
    return 0
  fi
  if [[ ! -f "${INIT_SCRIPT}" ]]; then
    print_tag "error" "init script not found: ${INIT_SCRIPT}"
    exit 1
  fi
  if [[ ${DRY_RUN} -eq 1 ]]; then
    print_tag "info" "dry-run: ensure local state under ${TARGET_WORKSPACE_ROOT}"
    return 0
  fi

  bash "${INIT_SCRIPT}" --target-root "${TARGET_WORKSPACE_ROOT}" --no-reset
}

merge_hooks() {
  local dst_hooks="${TARGET_DIR}/hooks.json"

  if [[ ${INCLUDE_HOOKS} -eq 0 ]]; then
    return 0
  fi
  if [[ ! -f "${HOOK_MANIFEST}" ]]; then
    print_tag "warn" "hook manifest not found: ${HOOK_MANIFEST}"
    return 0
  fi
  if [[ ! -f "${MERGE_HELPER}" ]]; then
    print_tag "error" "merge helper not found: ${MERGE_HELPER}"
    exit 1
  fi
  if [[ ! -f "${HOOK_SCRIPT}" ]]; then
    print_tag "error" "hook script not found: ${HOOK_SCRIPT}"
    exit 1
  fi

  if [[ ${DRY_RUN} -eq 1 ]]; then
    python3 "${MERGE_HELPER}" \
      --manifest "${HOOK_MANIFEST}" \
      --target "${dst_hooks}" \
      --hook-script "${HOOK_SCRIPT}" \
      --workspace-root "${TARGET_WORKSPACE_ROOT}" \
      --dry-run
  else
    python3 "${MERGE_HELPER}" \
      --manifest "${HOOK_MANIFEST}" \
      --target "${dst_hooks}" \
      --hook-script "${HOOK_SCRIPT}" \
      --workspace-root "${TARGET_WORKSPACE_ROOT}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      if [[ $# -lt 2 ]]; then
        print_tag "error" "--target requires a path"
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
    --no-init)
      INCLUDE_INIT=0
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
      print_tag "error" "unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

resolve_target_dir
resolve_target_workspace_root
ensure_local_state
require_rule_files
render_rules
merge_hooks

print_tag "done" "cursor runtime deployment complete"
