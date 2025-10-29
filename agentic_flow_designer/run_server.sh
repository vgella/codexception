#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Load shared environment variables if a .env is present one level up.
if [[ -f "${PROJECT_ROOT}/.env" ]]; then
  set -o allexport
  # shellcheck disable=SC1090
  source "${PROJECT_ROOT}/.env"
  set +o allexport
fi

export PYTHONUNBUFFERED=1

LOG_FILE="${SCRIPT_DIR}/server.log"
mkdir -p "$(dirname "${LOG_FILE}")"

# Stream logs both to stdout (so Codex can show them) and to a persistent file.
python3 "${SCRIPT_DIR}/server.py" 2>&1 | tee -a "${LOG_FILE}"
exit "${PIPESTATUS[0]}"
