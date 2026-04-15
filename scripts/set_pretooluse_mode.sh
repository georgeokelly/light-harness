#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
RED=""
GREEN=""
BLUE=""
ORANGE=""
RESET=""
TARGET_ROOT="."

if [[ -t 1 ]]; then
  RED=$'\033[31m'
  GREEN=$'\033[32m'
  BLUE=$'\033[34m'
  ORANGE=$'\033[38;5;208m'
  RESET=$'\033[0m'
fi

usage() {
  echo "Usage: bash scripts/set_pretooluse_mode.sh [--target-root <path>] <normal|sandbox|show>"
}

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
  print_tag "ok" "pre-tool-use mode set to $(format_mode "${mode}")"
  print_tag "info" "mode file: ${MODE_FILE}"
}

MODE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-root)
      if [[ $# -lt 2 ]]; then
        print_tag "error" "--target-root requires a path"
        usage
        exit 1
      fi
      TARGET_ROOT="$2"
      shift 2
      ;;
    normal|sandbox|show)
      if [[ -n "${MODE}" ]]; then
        print_tag "error" "mode already provided: ${MODE}"
        usage
        exit 1
      fi
      MODE="$1"
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

if [[ -z "${MODE}" ]]; then
  usage
  exit 1
fi

TARGET_ROOT_DIR="$(resolve_from_repo_root "${TARGET_ROOT}")"
MODE_FILE="${TARGET_ROOT_DIR}/.agent-memory/tmp/pretooluse-mode"

case "${MODE}" in
  normal)
    write_mode "normal"
    ;;
  sandbox)
    write_mode "sandbox"
    ;;
  show)
    print_tag "info" "pre-tool-use mode: $(format_mode "$(current_mode)")"
    print_tag "info" "mode file: ${MODE_FILE}"
    ;;
  *)
    print_tag "error" "unknown mode: ${MODE}"
    usage
    exit 1
    ;;
esac
