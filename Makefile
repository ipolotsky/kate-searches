.PHONY: up down web api worker beat lint test test-integration db-reset db-migrate db-types install seed-admin seed-looton

up:            ## поднять локальную инфру (Supabase CLI + Redis)
	supabase start
	docker compose up -d

down:          ## остановить инфру
	docker compose down
	supabase stop

install:       ## установить зависимости обоих сервисов
	cd apps/web && pnpm install
	cd services/api && pip install -e ".[dev]"

web:           ## dev-сервер фронта
	cd apps/web && pnpm dev

api:           ## dev-сервер api
	cd services/api && uvicorn app.main:app --reload

worker:        ## Celery worker (очереди default/fetch/extract/score/generate)
	cd services/api && celery -A app.worker.celery_app worker -Q default,fetch,extract,score,generate -l info

beat:          ## Celery beat (диспетчер дневных прогонов)
	cd services/api && celery -A app.worker.celery_app beat -l info

lint:          ## линты как в CI
	cd apps/web && pnpm lint
	cd services/api && ruff check . && ruff format --check .

test:          ## юнит-тесты как в CI (без БД и ключей провайдеров)
	cd apps/web && pnpm test
	cd services/api && pytest -q -m "not integration and not live"

test-integration: ## интеграционные тесты (нужен запущенный Supabase CLI стек)
	cd services/api && RUN_DB_TESTS=1 pytest -q -m integration

db-reset:      ## применить миграции к локальному Supabase (supabase/migrations/*)
	supabase db reset

db-migrate:    ## применить миграции к БД из DATABASE_URL (hosted Supabase)
	@for f in supabase/migrations/*.sql; do \
		echo "applying $$f"; \
		psql "$$DATABASE_URL" -f $$f; \
	done

db-types:      ## регенерировать типы Supabase для web (после изменения схемы)
	supabase gen types typescript --local --schema public > apps/web/src/lib/supabase/database.types.ts

seed-admin:    ## выдать платформенного (супер) админа по email: make seed-admin EMAIL=you@example.com [DB=<url>]
	@test -n "$(EMAIL)" || (echo "Требуется EMAIL=you@example.com (пользователь уже должен быть зарегистрирован)" && exit 1)
	psql "$(or $(DB),postgresql://postgres:postgres@localhost:54322/postgres)" \
		-c "insert into platform_admins (user_id) select id from users where email = '$(EMAIL)' on conflict do nothing;"
	@echo "platform_admins <- $(EMAIL)"

seed-looton:   ## залить пилот LOOTON, идемпотентно. Локально: make seed-looton. Прод: make seed-looton DB=<url> ARGS="--owner-email kate@..."
	cd services/api && DATABASE_URL="$(or $(DB),postgresql://postgres:postgres@localhost:54322/postgres)" \
		. .venv/bin/activate && python scripts/seed_looton.py $(or $(ARGS),--create)
