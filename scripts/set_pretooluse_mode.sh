#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODE_FILE="${ROOT_DIR}/.agent-memory/tmp/pretooluse-mode"
RED=""
GREEN=""
RESET=""

if [[ -t 1 ]]; then
  RED=$'\033[31m'
  GREEN=$'\033[32m'
  RESET=$'\033[0m'
fi

usage() {
  echo "Usage: bash scripts/set_pretooluse_mode.sh <normal|sandbox|show>"
}

color_for_mode() {
  local mode="$1"
  case "${mode}" in
    normal)
      printf '%s' "${GREEN}"
      ;;
    sandbox)
      printf '%s' "${RED}"
      ;;
    *)
      printf ''
      ;;
  esac
}

format_mode() {
  local mode="$1"
  local color=""
  color="$(color_for_mode "${mode}")"
  if [[ -n "${color}" && -n "${RESET}" ]]; then
    printf '%s%s%s' "${color}" "${mode}" "${RESET}"
  else
    printf '%s' "${mode}"
  fi
}

current_mode() {
  if [[ -f "${MODE_FILE}" ]]; then
    tr -d '[:space:]' < "${MODE_FILE}"
  else
    printf 'normal'
  fi
}

write_mode() {
  local mode="$1"
  mkdir -p "$(dirname "${MODE_FILE}")"
  printf '%s\n' "${mode}" > "${MODE_FILE}"
  echo "[ok] pre-tool-use mode set to $(format_mode "${mode}")"
  echo "[info] mode file: ${MODE_FILE}"
}

if [[ $# -ne 1 ]]; then
  usage
  exit 1
fi

case "$1" in
  normal)
    write_mode "normal"
    ;;
  sandbox)
    write_mode "sandbox"
    ;;
  show)
    echo "[info] pre-tool-use mode: $(format_mode "$(current_mode)")"
    ;;
  -h|--help)
    usage
    ;;
  *)
    echo "[error] unknown mode: $1"
    usage
    exit 1
    ;;
esac
