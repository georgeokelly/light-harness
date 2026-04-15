#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNINSTALL_HELPER="${SCRIPT_DIR}/uninstall_runtime_config.py"

if [[ ! -f "${UNINSTALL_HELPER}" ]]; then
  echo "[error] uninstall helper not found: ${UNINSTALL_HELPER}"
  exit 1
fi

python3 "${UNINSTALL_HELPER}" "$@"
