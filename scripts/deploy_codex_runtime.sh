#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
HOOK_MANIFEST="${ROOT_DIR}/config/hooks/codex.json"
MERGE_HELPER="${ROOT_DIR}/scripts/merge_runtime_config.py"

TARGET=".codex"
INCLUDE_HOOKS=1
INCLUDE_CONFIG=1
DRY_RUN=0

usage() {
  echo "Usage: bash scripts/deploy_codex_runtime.sh [--target <path>] [--no-hooks] [--no-config] [--dry-run]"
}

resolve_target_dir() {
  if [[ "${TARGET}" = /* ]]; then
    TARGET_DIR="${TARGET}"
  else
    TARGET_DIR="${ROOT_DIR}/${TARGET}"
  fi
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

ensure_feature_flag() {
  local config_path="${TARGET_DIR}/config.toml"
  local tmp_path=""

  if [[ ${INCLUDE_CONFIG} -eq 0 ]]; then
    return 0
  fi

  if [[ ${DRY_RUN} -eq 1 ]]; then
    echo "[dry-run] ensure codex_hooks = true in ${config_path}"
    return 0
  fi

  mkdir -p "$(dirname "${config_path}")"
  if [[ ! -f "${config_path}" ]]; then
    {
      printf '[features]\n'
      printf 'codex_hooks = true\n'
    } > "${config_path}"
    echo "[ok] wrote ${config_path}"
    return 0
  fi

  tmp_path="$(mktemp "${config_path}.XXXXXX")"
  awk '
    BEGIN {
      in_features = 0
      has_features = 0
      wrote_flag = 0
    }
    /^\[.*\]/ {
      if (in_features && !wrote_flag) {
        print "codex_hooks = true"
        wrote_flag = 1
      }
      if ($0 == "[features]") {
        has_features = 1
        in_features = 1
      } else {
        in_features = 0
      }
      print
      next
    }
    {
      if (in_features && $0 ~ /^[[:space:]]*codex_hooks[[:space:]]*=/) {
        if (!wrote_flag) {
          print "codex_hooks = true"
          wrote_flag = 1
        }
        next
      }
      print
    }
    END {
      if (!has_features) {
        print ""
        print "[features]"
        print "codex_hooks = true"
      } else if (in_features && !wrote_flag) {
        print "codex_hooks = true"
      }
    }
  ' "${config_path}" > "${tmp_path}"
  mv "${tmp_path}" "${config_path}"
  echo "[ok] ensured codex_hooks = true in ${config_path}"
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
    --no-config)
      INCLUDE_CONFIG=0
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
ensure_feature_flag

echo "[done] codex runtime deployment complete"
