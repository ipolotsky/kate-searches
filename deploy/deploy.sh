#!/usr/bin/env bash
# Выкатка одного окружения на VM. Usage: deploy.sh <prod|staging> <web_tag> <api_tag>
set -euo pipefail

ENVN="${1:?usage: deploy.sh <prod|staging> <web_tag> <api_tag>}"
WEB_TAG="${2:?web tag required}"
API_TAG="${3:?api tag required}"

ROOT="/srv/kate-searches"
DIR="$ROOT/$ENVN"

if [ ! -f "$DIR/.env" ]; then
  echo "missing $DIR/.env" >&2
  exit 1
fi

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
