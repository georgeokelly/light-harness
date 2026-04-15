#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOK_MANIFEST="${ROOT_DIR}/config/hooks/claude.json"
MERGE_HELPER="${ROOT_DIR}/scripts/merge_runtime_config.py"
INIT_SCRIPT="${ROOT_DIR}/scripts/init_local_state.sh"
HOOK_SCRIPT="${ROOT_DIR}/scripts/light_harness_hook.py"

TARGET=".claude"
SETTINGS_SCOPE="local"
INCLUDE_HOOKS=1
INCLUDE_INIT=1
DRY_RUN=0
RED=""
GREEN=""
BLUE=""
ORANGE=""
RESET=""

usage() {
  echo "Usage: bash scripts/deploy_claude_runtime.sh [--target <path>] [--scope local|project] [--no-hooks] [--no-init] [--dry-run]"
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

settings_file_name() {
  if [[ "${SETTINGS_SCOPE}" = "project" ]]; then
    printf 'settings.json'
  else
    printf 'settings.local.json'
  fi
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
  local dst_settings="${TARGET_DIR}/$(settings_file_name)"

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
      --target "${dst_settings}" \
      --hook-script "${HOOK_SCRIPT}" \
      --workspace-root "${TARGET_WORKSPACE_ROOT}" \
      --dry-run
  else
    python3 "${MERGE_HELPER}" \
      --manifest "${HOOK_MANIFEST}" \
      --target "${dst_settings}" \
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
    --scope)
      if [[ $# -lt 2 ]]; then
        print_tag "error" "--scope requires a value"
        usage
        exit 1
      fi
      SETTINGS_SCOPE="$2"
      if [[ "${SETTINGS_SCOPE}" != "local" && "${SETTINGS_SCOPE}" != "project" ]]; then
        print_tag "error" "--scope must be one of: local, project"
        exit 1
      fi
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
merge_hooks

print_tag "done" "claude runtime deployment complete"
