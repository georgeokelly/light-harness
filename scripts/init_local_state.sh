#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PRE_TEMPLATE="${ROOT_DIR}/templates/light-harness-preflight.md"
REC_TEMPLATE="${ROOT_DIR}/templates/light-harness-record.md"

FORCE=0
TARGET_ROOT="."
STATE_DIR_INPUT=""
RESET_FLAG=1
RED=""
GREEN=""
BLUE=""
ORANGE=""
RESET=""

usage() {
  echo "Usage: bash scripts/init_local_state.sh [--force] [--no-reset] [--target-root <path>] [--state-dir <path>]"
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

resolve_from_repo_root() {
  local path="$1"
  if [[ "${path}" = /* ]]; then
    printf '%s' "${path}"
  else
    printf '%s' "${ROOT_DIR}/${path}"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      shift
      ;;
    --no-reset)
      RESET_FLAG=0
      shift
      ;;
    --target-root)
      if [[ $# -lt 2 ]]; then
        print_tag "error" "--target-root requires a path"
        usage
        exit 1
      fi
      TARGET_ROOT="$2"
      shift 2
      ;;
    --state-dir)
      if [[ $# -lt 2 ]]; then
        print_tag "error" "--state-dir requires a path"
        usage
        exit 1
      fi
      STATE_DIR_INPUT="$2"
      shift 2
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

TARGET_ROOT_DIR="$(resolve_from_repo_root "${TARGET_ROOT}")"
if [[ -n "${STATE_DIR_INPUT}" ]]; then
  if [[ "${STATE_DIR_INPUT}" = /* ]]; then
    STATE_DIR="${STATE_DIR_INPUT}"
  else
    STATE_DIR="${TARGET_ROOT_DIR}/${STATE_DIR_INPUT}"
  fi
else
  STATE_DIR="${TARGET_ROOT_DIR}/.agent-memory/records/current"
fi

PRE_TARGET="${STATE_DIR}/preflight.md"
REC_TARGET="${STATE_DIR}/record.md"
CODE_CHANGE_FLAG="${STATE_DIR}/_code_change.flag"

copy_template() {
  local src="$1"
  local dst="$2"

  if [[ ! -f "${src}" ]]; then
    print_tag "error" "template not found: ${src}"
    exit 1
  fi

  if [[ -f "${dst}" && ${FORCE} -eq 0 ]]; then
    print_tag "skip" "exists: ${dst}"
    return 0
  fi

  mkdir -p "$(dirname "${dst}")"
  cp "${src}" "${dst}"
  print_tag "ok" "wrote: ${dst}"
}

mkdir -p "${STATE_DIR}"
print_tag "ok" "ensured directory: ${STATE_DIR}"
print_tag "info" "target root: ${TARGET_ROOT_DIR}"

copy_template "${PRE_TEMPLATE}" "${PRE_TARGET}"
copy_template "${REC_TEMPLATE}" "${REC_TARGET}"

if [[ ${RESET_FLAG} -eq 1 ]]; then
  # Reset per-task marker to avoid stale reasoning-chain checks.
  : > "${CODE_CHANGE_FLAG}"
  print_tag "ok" "reset: ${CODE_CHANGE_FLAG}"
else
  print_tag "skip" "reset flag disabled: ${CODE_CHANGE_FLAG}"
fi

print_tag "done" "local state initialization complete"
