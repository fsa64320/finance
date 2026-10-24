#!/usr/bin/env bash
# Démarre le backend (avec l'interface compilée) sur une base neuve, pour les tests de bout en bout.
# Usage : server.sh <port>
set -euo pipefail

PORT="$1"
FRONTEND="$(cd "$(dirname "$0")/../.." && pwd)"
DATA="${FRONTEND}/.e2e-data/${PORT}"

rm -rf "${DATA}"
mkdir -p "${DATA}"

cd "${FRONTEND}/../backend"
FINANCE_DATA_DIR="${DATA}" \
FINANCE_STATIC_DIR="${FRONTEND}/dist" \
FINANCE_HOST=127.0.0.1 \
FINANCE_PORT="${PORT}" \
  exec uv run --frozen python -m finance
