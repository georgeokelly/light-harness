#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

STATE_DIR="${ROOT_DIR}/.agent-memory/records/current"
PRE_TEMPLATE="${ROOT_DIR}/templates/light-harness-preflight.md"
REC_TEMPLATE="${ROOT_DIR}/templates/light-harness-record.md"
PRE_TARGET="${STATE_DIR}/preflight.md"
REC_TARGET="${STATE_DIR}/record.md"
CODE_CHANGE_FLAG="${STATE_DIR}/_code_change.flag"

FORCE=0

usage() {
  echo "Usage: bash scripts/init_local_state.sh [--force]"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
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

copy_template() {
  local src="$1"
  local dst="$2"

  if [[ ! -f "${src}" ]]; then
    echo "[error] template not found: ${src}"
    exit 1
  fi

  if [[ -f "${dst}" && ${FORCE} -eq 0 ]]; then
    echo "[skip] exists: ${dst}"
    return 0
  fi

  mkdir -p "$(dirname "${dst}")"
  cp "${src}" "${dst}"
  echo "[ok] wrote: ${dst}"
}

mkdir -p "${STATE_DIR}"
echo "[ok] ensured directory: ${STATE_DIR}"

copy_template "${PRE_TEMPLATE}" "${PRE_TARGET}"
copy_template "${REC_TEMPLATE}" "${REC_TARGET}"

# Reset per-task marker to avoid stale reasoning-chain checks.
: > "${CODE_CHANGE_FLAG}"
echo "[ok] reset: ${CODE_CHANGE_FLAG}"

echo "[done] local state initialization complete"
