.PHONY: up down web api worker beat lint test test-integration db-reset db-migrate install

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
