.PHONY: up down web api lint test db-migrate install

up:            ## поднять локальную инфру (postgres + redis)
	docker compose up -d

down:          ## остановить инфру
	docker compose down

install:       ## установить зависимости обоих сервисов
	cd apps/web && pnpm install
	cd services/api && pip install -e ".[dev]"

web:           ## dev-сервер фронта
	cd apps/web && pnpm dev

api:           ## dev-сервер api
	cd services/api && uvicorn app.main:app --reload

lint:          ## линты как в CI
	cd apps/web && pnpm lint
	cd services/api && ruff check . && ruff format --check .

test:          ## тесты как в CI
	cd apps/web && pnpm test
	cd services/api && pytest -q

db-migrate:    ## применить миграции к локальной БД
	@for f in supabase/migrations/*.sql; do \
		echo "applying $$f"; \
		psql "$${DATABASE_URL:-postgresql://kate:kate@localhost:5432/katesearches}" -f $$f; \
	done
