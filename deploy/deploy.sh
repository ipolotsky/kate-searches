#!/usr/bin/env bash
# Выкатка одного окружения на VM. Usage: deploy.sh <prod|stage> <web_tag> <api_tag>
set -euo pipefail

ENVN="${1:?usage: deploy.sh <prod|stage> <web_tag> <api_tag>}"
WEB_TAG="${2:?web tag required}"
API_TAG="${3:?api tag required}"

ROOT="/srv/kate-searches"
DIR="$ROOT/$ENVN"

if [ ! -f "$DIR/.env" ]; then
  echo "missing $DIR/.env" >&2
  exit 1
fi

# --- Сеть obs (общая для app + observability) ---
if ! docker network inspect obs >/dev/null 2>&1; then
  docker network create obs
fi

# --- Observability stack (общий на prod + stage) ---
# Домены берём из существующих .env окружений, basic-auth — из GitHub secret VL_BASIC_AUTH.
OBS_DIR="$ROOT/observability"

if [ -f "$OBS_DIR/compose.yml" ]; then
  if [ -z "${VL_BASIC_AUTH:-}" ]; then
    echo "WARNING: VL_BASIC_AUTH not set — observability stack skipped" >&2
  else
    # Читаем DOMAIN из .env каждого окружения
    if [ -f "$ROOT/prod/.env" ]; then
      PROD_OBS_DOMAIN="$(grep -E '^DOMAIN=' "$ROOT/prod/.env" | cut -d= -f2- || true)"
    fi
    if [ -f "$ROOT/stage/.env" ]; then
      STAGING_OBS_DOMAIN="$(grep -E '^DOMAIN=' "$ROOT/stage/.env" | cut -d= -f2- || true)"
    fi

    if [ -n "${PROD_OBS_DOMAIN:-}" ] || [ -n "${STAGING_OBS_DOMAIN:-}" ]; then
      cd "$OBS_DIR"
      export COMPOSE_FILE=compose.yml
      export COMPOSE_PROJECT_NAME=observability
      export PROD_OBS_DOMAIN STAGING_OBS_DOMAIN
      if ! docker compose up -d; then
        echo "WARNING: observability stack failed to start — logs will not be collected" >&2
      fi
      cd "$DIR"
    fi
  fi
fi

# --- App stack ---
# держим compose рядом с .env: project directory резолвится в $DIR, env_file: .env -> $DIR/.env
cp "$ROOT/compose.yml" "$DIR/compose.yml"
cd "$DIR"

# пинним теги свежих образов в .env (идемпотентный upsert)
if grep -q '^WEB_TAG=' .env; then
  sed -i "s|^WEB_TAG=.*|WEB_TAG=$WEB_TAG|" .env
else
  echo "WEB_TAG=$WEB_TAG" >> .env
fi
if grep -q '^API_TAG=' .env; then
  sed -i "s|^API_TAG=.*|API_TAG=$API_TAG|" .env
else
  echo "API_TAG=$API_TAG" >> .env
fi

export COMPOSE_FILE=compose.yml
export COMPOSE_PROJECT_NAME="$(grep -E '^STACK=' .env | cut -d= -f2-)"

docker compose pull
docker compose up -d redis

# zero-downtime rollout для stateless HTTP; при первом деплое сервиса — обычный up
roll() {
  local svc="$1"
  if [ -n "$(docker compose ps -q "$svc" 2>/dev/null)" ]; then
    docker rollout -f compose.yml "$svc"
  else
    docker compose up -d "$svc"
  fi
}

roll api
roll web

# worker — обычный recreate (warm shutdown, in-flight задачи переживут в Redis);
# beat — строго синглтон, только recreate, никогда rollout.
docker compose up -d --no-deps --force-recreate worker
docker compose up -d --no-deps --force-recreate beat

docker image prune -f
