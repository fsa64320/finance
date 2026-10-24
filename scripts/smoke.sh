#!/usr/bin/env bash
# Test de fumée de l'image (T119, SC-006) : construit l'image, démarre un conteneur avec un volume
# temporaire, crée l'accès, enregistre une donnée, redémarre et la relit.
#
# Usage : scripts/smoke.sh          (Docker doit tourner ; port local 18000, ou SMOKE_PORT)
set -euo pipefail

cd "$(dirname "$0")/.."

IMAGE="finance:smoke"
SUFFIX="$$"
NAME="finance-smoke-${SUFFIX}"
VOLUME="finance-smoke-data-${SUFFIX}"
PORT="${SMOKE_PORT:-18000}"
BASE="http://127.0.0.1:${PORT}/api/v1"
JAR="$(mktemp)"
# Mot de passe jetable, propre à ce test.
PASSWORD="fumee-$(date +%s)-horizon-bleu"

cleanup() {
  docker rm -f "${NAME}" >/dev/null 2>&1 || true
  docker volume rm "${VOLUME}" >/dev/null 2>&1 || true
  rm -f "${JAR}"
}
trap cleanup EXIT

fail() {
  echo "ÉCHEC : $*" >&2
  docker logs "${NAME}" 2>&1 | tail -n 20 >&2 || true
  exit 1
}

wait_ready() {
  for _ in $(seq 1 60); do
    if curl -fsS "${BASE}/auth/status" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  fail "le conteneur ne répond pas après 60 secondes"
}

expect() { # expect <description> <attendu> <réel>
  if [ "$2" != "$3" ]; then
    fail "$1 : attendu « $2 », reçu « $3 »"
  fi
  echo "ok - $1"
}

status_of() { curl -sS -o /dev/null -w '%{http_code}' "$@"; }

echo "== Construction de l'image"
docker build --quiet -t "${IMAGE}" . >/dev/null

echo "== Démarrage (volume temporaire ${VOLUME})"
docker volume create "${VOLUME}" >/dev/null
docker run -d --name "${NAME}" -p "127.0.0.1:${PORT}:8000" -v "${VOLUME}:/data" "${IMAGE}" >/dev/null
wait_ready

expect "aucun accès créé au départ" '{"state":"uninitialized"}' "$(curl -sS "${BASE}/auth/status")"
expect "le processus ne tourne pas en root" "10001" "$(docker exec "${NAME}" id -u)"
expect "l'interface est servie" "200" "$(status_of "http://127.0.0.1:${PORT}/")"
expect "les données sont refusées sans accès" "401" "$(status_of "${BASE}/accounts")"

echo "== Création de l'accès et d'une donnée"
expect "création du mot de passe" "204" "$(status_of -c "${JAR}" -X POST "${BASE}/auth/setup" \
  -H 'Content-Type: application/json' -d "{\"password\":\"${PASSWORD}\"}")"
expect "création d'un compte" "201" "$(status_of -b "${JAR}" -X POST "${BASE}/accounts" \
  -H 'Content-Type: application/json' \
  -d '{"type":"PEA","name":"Compte de fumée","opened_on":"2026-01-02"}')"

echo "== Redémarrage"
docker restart "${NAME}" >/dev/null
wait_ready
expect "instance verrouillée après redémarrage" '{"state":"locked"}' "$(curl -sS "${BASE}/auth/status")"
expect "mauvais mot de passe refusé" "401" "$(status_of -X POST "${BASE}/auth/unlock" \
  -H 'Content-Type: application/json' -d '{"password":"mauvais-mot-de-passe-12"}')"
expect "déverrouillage" "204" "$(status_of -c "${JAR}" -X POST "${BASE}/auth/unlock" \
  -H 'Content-Type: application/json' -d "{\"password\":\"${PASSWORD}\"}")"

accounts="$(curl -sS -b "${JAR}" "${BASE}/accounts")"
case "${accounts}" in
  *"Compte de fumée"*) echo "ok - la donnée est relue après redémarrage" ;;
  *) fail "le compte a disparu après redémarrage : ${accounts}" ;;
esac

echo "== Base chiffrée au repos"
if docker run --rm -v "${VOLUME}:/data:ro" --entrypoint sh "${IMAGE}" \
  -c 'grep -q "SQLite format 3" /data/finance.db'; then
  fail "le fichier de base est lisible en clair"
fi
echo "ok - le fichier de base n'est pas du SQLite en clair"

echo "Test de fumée réussi."
