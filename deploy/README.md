# Деплой на VM (prod + staging)

Прод и staging крутятся на одной VM двумя изолированными compose-проектами (`kate-prod`, `kate-stage`): свои сети, контейнеры, Redis и `.env`. Общий Traefik держит TLS и разводит по хостнеймам. Образы собираются в GitHub Actions и пушатся в GHCR, VM только `pull` + `docker rollout`.

Реком. VM: 4 vCPU / 8 GB RAM / 40+ GB SSD + 2-4 GB swap.

## Что катим и как

- `web`, `api` — stateless HTTP, катятся через `docker rollout` (zero-downtime: scale-up, ждём healthcheck, scale-down).
- `worker` — recreate с warm shutdown; in-flight задачи переживут в Redis (`acks_late` + `reject_on_worker_lost`).
- `beat` — строго один экземпляр, только recreate, никогда rollout (иначе два планировщика).
- `redis` — по одному на окружение, брокер Celery, без персистентности.

## Разовая подготовка VM

1. Docker + docker compose v2.
2. Плагин docker-rollout:
   ```bash
   mkdir -p ~/.docker/cli-plugins
   curl -fsSL https://raw.githubusercontent.com/wowu/docker-rollout/master/docker-rollout \
     -o ~/.docker/cli-plugins/docker-rollout
   chmod +x ~/.docker/cli-plugins/docker-rollout
   ```
3. Swap 2-4 GB (при 8 GB RAM это страховка на время rollout, когда web/api временно задваиваются).
4. Общая сеть проксирования: `docker network create proxy`.
5. Traefik:
   ```bash
   mkdir -p /srv/traefik && cd /srv/traefik
   # положить сюда deploy/traefik/docker-compose.yml
   touch acme.json && chmod 600 acme.json
   docker compose up -d
   ```
6. Раскладка стека и секретов:
   ```bash
   mkdir -p /srv/kate-searches/prod /srv/kate-searches/stage
   # положить deploy/compose.yml и deploy/deploy.sh в /srv/kate-searches/
   chmod +x /srv/kate-searches/deploy.sh
   # заполнить руками, chmod 600:
   #   /srv/kate-searches/prod/.env      (по образцу deploy/env.example, STACK=kate-prod, DOMAIN=taskyou.me)
   #   /srv/kate-searches/stage/.env   (STACK=kate-stage, DOMAIN=stage.taskyou.me, свой Supabase-проект)
   chmod 600 /srv/kate-searches/prod/.env /srv/kate-searches/stage/.env
   ```
7. DNS: A-записи `taskyou.me` и `stage.taskyou.me` на IP VM. Переезд на `katesearch.es` позже — сменить `DOMAIN` в `.env`, добавить A-записи, Traefik перевыпустит сертификат.
8. Второй проект Supabase под staging: создать, прогнать миграции (`DATABASE_URL=<staging-db> make db-migrate`), взять URL/anon/service-role в `staging/.env`.

`compose.yml` и `deploy.sh` дальше синхронизируются автоматически из репозитория на шаге деплоя (scp), править их руками на VM не нужно.

## Ручной выкат (для отладки)

```bash
/srv/kate-searches/deploy.sh stage stage-<sha> stage-<sha>
/srv/kate-searches/deploy.sh prod prod-<sha> prod-<sha>
```
