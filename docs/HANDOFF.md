# HANDOFF — переход в Claude Code

Этот скелет собран в Cowork. Дальше работаем в Claude Code на твоей машине (нужен твой git, docker, Flowbite MCP).

## 1. Поставить Claude Code (Mac)

```bash
curl -fsSL https://claude.ai/install.sh | bash     # или: brew install --cask claude-code
cd ~/Develop/KateSearches/KateSearches
claude
```

## 2. Запушить в GitHub (из Claude Code — там есть твой git-auth)

Локальный коммит уже сделан. Останется:

```bash
git remote add origin https://github.com/ipolotsky/kate-searches.git
git branch -M main
git push -u origin main
```

## 3. Подключить Flowbite MCP

Скопируй `docs/mcp.example.json` → `.mcp.json` в корень и подставь команду запуска MCP-сервера внутри контейнера `flowbite-mcp-pro-100`. Claude Code подхватит сервер при следующем старте.

## 4. Поднять локально

```bash
make up                 # postgres + redis
make db-migrate         # схема
make install            # зависимости web + api
make web                # фронт :3000
make api                # api  :8000
make lint && make test  # как в CI
```

## 5. Что проверить первым делом (smoke)

- `apps/web`: `pnpm install` ставится, `pnpm dev` поднимает `/en/dashboard` и `/ru/dashboard`, `pnpm test` зелёный (i18n-ключи совпадают).
- `services/api`: `pip install -e ".[dev]"`, `uvicorn app.main:app` отдаёт `/health`, `pytest` зелёный.
- Свериться с CI/CD-паттерном из `~/Develop/Mountly/TestTask` и при желании подогнать `.github/workflows/`.

## 6. Дальше по плану (M0→M4)

См. `04_mvp_spec.md` §7 и чек-лист в `CLAUDE.md`. Первый содержательный шаг — подключить реальный LLM-вызов в `app/llm/client.py` и БД-слой, затем M1 (ingestion: RSS+sitemap+Crawl4AI).

## Ждём от Kate

Примеры её реальных статей с указанием инфоповода-источника — это few-shot для брендового голоса (стадия генерации).
