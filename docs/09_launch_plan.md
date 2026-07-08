# 09 - План запуска: ревью, триал, уведомления, Stripe, UX

Источник: независимое ревью кодовой базы (7 измерений, каждая находка адверсариально верифицирована по реальному коду) плюс research по best practices free-trial, Resend и Stripe test-mode. Числа и решения ниже зафиксированы владельцем.

## Зафиксированные решения

1. Триал: гибрид, срабатывает первый достигнутый лимит - 7 дней, $3 hard-cap по бюджету, 10 черновиков, 3 источника. Все числа конфигурируемы из админки, это стартовые дефолты. Guardrail: потолок триального бюджета max $10 на строке тенанта.
2. Воронка: карта вперёд, native Stripe `trial_period_days`. Триал начинается через Stripe Checkout. Внутренний ledger при этом продолжает энфорсить COGS-cap $3 на время `trialing` (страховка от фарма до конверсии).
3. Уведомления Resend в первый заход: ежедневный дайджест, trial-ending, budget-threshold (50/80/100%), welcome/онбординг.
4. Launch-blocker багфиксы гейтят боевой запуск: чиним до реальных пользователей и до прода.
5. Stripe запускаем в test mode на проде, остальное в боевом режиме. Флип test to live - заменой секретов без изменений кода.

## Открытая развилка (test mode plus карта-вперёд)

В Stripe test mode проходят только тестовые карты (`4242...`), поэтому реальный публичный пользователь не завершит card-first checkout. Варианты на окно test-mode:

- Вариант A (по умолчанию): в окне test-mode воронку валидируем на пилоте и приглашённых через тестовые карты; публичную рекламную кампанию «попробовать бесплатно» запускаем после флипа на live-ключи. Проще всего, соответствует «test mode сейчас, кампания позже».
- Вариант B: на окно test-mode добавить no-card app-enforced триал (дефолтный pilot-state плюс `trial_ends_at`, те же caps $3/10/3) для реальной публики, ретайрим при флипе.

CTA на странице тарифов выводится из префикса publishable-ключа (`pk_test_` против `pk_live_`), так что переключение витрины между режимами автоматическое. Решение по A/B - за владельцем.

## Ревью: 13 подтверждённых находок

Severity в скобках. RLS/мультитенант, платформенные админы, chord-барьеры ingestion, атомарный claim генерации, provisioning тенанта - чисто, находок нет.

### Launch-blockers (деньги, безопасность, деплой) - milestone M6.1, гейт прода

1. (HIGH, деньги) `services/api/app/llm/client.py:97`. Падение записи `ai_usage`/settle после успешного LLM-вызова не возвращает резерв, статья откатывается в `scored` и перегенерится - двойное списание провайдеру, ledger блокирует тенант при почти нулевом видимом расходе, три книги расходятся. Фикс: bookkeeping после оплаченного вызова сделать non-fatal (успешный draft всё равно возвращает результат и advance в `drafted`), плюс фоновый reaper для утёкших резервов.
2. (HIGH, деньги) `services/api/app/worker/tasks.py:459`. Медленный (не мёртвый) прогон более 30 мин переспавнивается вторым параллельным пайплайном того же `run_id`; у скоринга нет pre-LLM claim, оба прогона скорят одни статьи - 2x расход и 2x резерв. Фикс: pre-LLM атомарный claim `extracted to scoring` (как у генерации `scored to drafting`), плюс CAS на re-dispatch stale-прогона.
3. (HIGH, деньги плюс данные) `services/api/app/pipeline/generation.py:170`. `release_draft_claim` только в except LLM-вызова; падение транзакции персиста поста или краш оставляет статью в `drafting` навсегда, деньги списаны, поста нет, reaper отсутствует. Фикс: release при любом падении после успешного вызова плюс reaper статей, застрявших в `drafting`.
4. (HIGH, SSRF) `services/api/app/adapters/rss.py:59`. Guard проверяет только исходный URL, `feedparser.parse()` сам резолвит DNS и следует редиректам без per-hop проверки. Фикс: качать байты фида через `safe_get`, отдавать в `feedparser.parse(content)`; IP-pinning; явный таймаут.
5. (HIGH, SSRF) `services/api/app/fetch/crawl4ai_fetcher.py:32`. Headless-браузер следует редиректам и резолвит DNS сам; достижимо через `render_js=true`. Фикс: locked-down egress (блок RFC1918/link-local/loopback на сетевом слое) или re-validate `result.url` после фетча.
6. (HIGH, деплой) `Makefile:44`. `db-migrate` без `ON_ERROR_STOP=1` и `set -e` - падение миграции даёт exit 0, деплой едет на немигрированную прод-БД. Фикс: `psql -v ON_ERROR_STOP=1` плюс fail-fast, лучше tracked-runner по новым миграциям.
12. (MEDIUM, деплой) `services/api/app/main.py:12`. `/health` статичный, не трогает БД/Redis; healthcheck-gated rollout переключит трафик на контейнер с мёртвой БД. Фикс: реальная проба `SELECT 1` плюс Redis PING, web `/api/health` - upstream-проба API.

Прерогатива триала: тугой $3-cap требует гейтить и scoring через ledger, а это упирается в фикс находки 7 (застревание в `extracted`) и находки 2. Поэтому 7 добавлена в M6.1.

7. (MEDIUM) `services/api/app/llm/client.py:75`. Скоринг тоже идёт через ledger-reserve вопреки доке «гейтим только генерацию»; при добитом ledger каждый score падает в `BudgetExceededError`, глотается как `skipped`, статьи навсегда в `extracted` (reaper нет). Фикс: для триала осознанно гейтить scoring плюс reaper пере-скоринга `extracted` после сброса периода; вне триала - не гейтить дешёвые стадии.

### Security-hardening (SSRF) - в M6.1

10. (MEDIUM, SSRF) `services/api/app/worker/robots.py:21`. `robots.txt` качается сырым `httpx.get(follow_redirects=True)` без guard и до основного фетча. Фикс: через `safe_get`.
11. (MEDIUM, SSRF) `services/api/app/fetch/guard.py:57`. Нет IP-pinning: guard валидирует хост, httpx резолвит DNS заново (TOCTOU/DNS-rebinding). Фикс: резолв один раз в guard, коннект на pinned IP.

### Корректность и целостность - milestone M6.4, не блокеры

8. (MEDIUM) `services/api/app/adapters/sitemap.py:107`. В sitemap-index падение дочернего sitemap двигает курсор вперёд - записи упавшего ребёнка теряются. Фикс: не двигать `last_published_at` при `child_fetch_error` (ретрай источника либо advance только при полном успехе).
9. (MEDIUM) `services/api/app/llm/client.py:80`. Instructor при провале валидации делает доп. платные вызовы (default до 4 попыток), `completion_cost` считает только финальный - hard-cap недосчитывает до 2-4x. Фикс: учитывать usage всех попыток либо ограничить попытки.
13. (LOW) `apps/web/src/app/[locale]/(app)/_actions/posts.ts:73`. `updatePostStatus` без compare-and-swap: конкурентные легальные переходы дают запрещённое состояние. Фикс: `.eq("status", from)` плюс проверка affected-row.

## Workstream 0. UX-фикс (быстро, изолированно, без бэкенда)

Причина зазора: shell зажат в `mx-auto max-w-7xl` в `apps/web/src/app/[locale]/(app)/layout.tsx:53`.

- Убрать `mx-auto max-w-7xl` с внешнего flex, shell на всю ширину, `aside` прижат к левому краю, full-height, `border-r`.
- Контенту воздух со всех сторон: `main` перевести с `px-4 py-6` на `px-6 py-8 lg:px-8`, добавить верхний отступ.
- Внутренний `max-w-6xl` на содержимое `main` для читабельности длинных страниц (сайдбар остаётся у края).
- Upsell-баннер перенести внутрь колонки контента.

Файлы: `layout.tsx`, `AppSidebar.tsx`. Milestone M6.0, выкатывается первым.

## Workstream 1 plus 3. Биллинг plus триал (слиты, т.к. триал стартует через Stripe)

Разделение ответственности: Stripe - источник правды по плану и статусу подписки; наш ledger - энфорс COGS по факту расхода; мост между ними одно число `tenants.ai_budget_usd_month`.

Механика триала:

- Вход: страница тарифов - Stripe Checkout (`mode=subscription`, price выбранного тира, `subscription_data.trial_period_days=7`, `client_reference_id=tenant_id`).
- Webhook `customer.subscription.created`/`updated`:
  - `trialing`: `plan` = выбранный тир, но `ai_budget_usd_month` = триальный cap ($3), статус `trialing`, зеркалим `trial_end` в `trial_ends_at`. Лимиты 10 черновиков и 3 источника действуют на время триала.
  - `active` (триал сконвертился, первый invoice оплачен): `ai_budget_usd_month` = бюджет тира, лимиты подняты до тира.
  - `past_due`: доступ держим, уведомляем.
  - `canceled`/`unpaid`: даунгрейд в pilot (free floor).
- Ledger при `trialing` использует фиксированный `period='trial'` (непополняемый пул на всё окно, иначе триал на стыке месяцев рефилит бюджет), при `active` - `YYYY-MM`. `reserve_budget`/`settle_budget`/`ledger_month_spent` без правок.
- На время триала scoring гейтится через ledger (единый $3-cap ограничивает суммарный COGS) - требует фиксов находок 2 и 7.
- Счётчики черновиков (10) и источников (3) - отдельные counters, не бюджетная механика: черновики в generation-пути, источники на создание в web-action.

Безопасность test-mode:

- Fail-fast на буте: ассерт `sk_test_` в режиме soft-launch плюс `model_validator` на совпадение режима ключей.
- Site-wide баннер «TEST MODE», выводимый из префикса publishable-ключа, а не из отдельной переменной.
- Checkout за auth плюс allowlist (`tenants.billing_enabled`), чтобы случайный юзер не ввёл реальную карту в test-форму.
- Отключить Stripe-письма в test.

Вебхуки и их маппинг:

- `checkout.session.completed` - привязать `stripe_customer_id`/`stripe_subscription_id` к тенанту.
- `customer.subscription.created`/`updated` - рабочая лошадка: `price to plan to budget`, выставить план, бюджет, статус, `current_period_end`.
- `customer.subscription.deleted` - даунгрейд в pilot.
- `invoice.paid` - подтверждение периода, `invoice.payment_failed` - `past_due` плюс письмо.
- Дедуп по `event.id` (таблица `stripe_events`), idempotency-ключи на исходящих create-вызовах.

Флип test to live: заменить секреты (`sk_`, `pk_`, `whsec_`, три `price_`) плюс редеплой плюс одноразовый re-provisioning пилотных тенантов в pilot (test-подписки в live не переносятся). Ноль изменений в коде.

Админка (расширить `PlanBudgetForm` плюс `admin.ts`): задавать и продлевать и отзывать `trial_ends_at`, триальный бюджет и лимиты per-tenant; глобальные дефолты в конфиге; guardrail потолок триала max $10.

Анти-абьюз: card-first сам по себе снимает основную массу (карта = идентичность плюс fraud-сигнал). Дёшево добавить: `users.email_normalized` (схлопнуть gmail `+suffix`/точки) с UNIQUE и блок disposable-доменов на регистрации - обязательны только если выбран вариант B (no-card окно).

Новый модуль `services/api/app/billing/`: `StripeSettings` (is_live из префикса), Checkout Session, Billing Portal, webhook-хендлер. Маппинг `PRICE_TO_PLAN` плюс `PLAN_BUDGET_USD` из `docs/06`, price-иды через env. Milestone M6.2.

## Workstream 2. Email-уведомления через Resend

Слать всё из Python/Celery. Шаблоны MJML через `mrml` плюс Jinja2 (нативно в Python, без Node в воркере, responsive, ru/en). Дайджест через Batch API чанками по 100 (не Broadcasts - контент персональный). Resend Pro $20 (Free с потолком 100 писем/день опасен для дайджеста).

- Новый модуль `services/api/app/email/client.py` (обёртка над `resend` SDK по образцу `llm/client.py`), отдельная Celery-очередь `emails`.
- Уведомления: дайджест ежедневно после `finalize_run` (`dedup_key=run_id`); welcome при регистрации; trial-ending за 2 дня до `trial_ends_at` и при достижении лимита; budget-threshold 50/80/100% на существующей эскалации `usageLevel`; payment-failed из Stripe-вебхука.
- Надёжность: durable-гард `email_dispatch_log` insert-before-send плюс Resend `Idempotency-Key`; pre-send фильтр по suppression плюс preferences во всех путях.
- Вебхуки и compliance: FastAPI-хендлер с Svix-верификацией по сырому телу; подписка на `bounced`/`complained`/`delivered`; one-click `List-Unsubscribe` на дайджест; GET `/unsubscribe` страница в Next.js.
- DNS: поддомен `mail.`, DKIM плюс SPF плюс DMARC (`p=none` на старт).
- Config: `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`, `EMAIL_FROM`, `APP_BASE_URL`.

Milestone M6.3, зависит от M6.2 (trial-ending, budget-threshold).

## Сводка изменений схемы

- `0007_billing.sql`: на `tenants` - `stripe_customer_id`, `stripe_subscription_id`, `subscription_status`, `current_period_end`, `trial_ends_at`, `billing_enabled`, опц. `trial_drafts_limit`/`trial_sources_limit`; control-таблица `stripe_events(event_id pk)` (пишет только service_role). Опц. `users.email_normalized` UNIQUE при варианте B.
- `0008_email.sql`: `email_preferences` (per-type тумблеры, `unsubscribe_token`, consent), `email_suppression` (email глобально unique, из вебхуков), `email_dispatch_log` (unique `(user_id, notification_type, dedup_key)`). Все с `tenant_id` плюс RLS, control-дисциплина как у `tenant_budget_ledger`.

## Новые переменные окружения

- API: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STARTER`, `STRIPE_PRICE_PRO`, `STRIPE_PRICE_AGENCY`, `RESEND_API_KEY`, `RESEND_WEBHOOK_SECRET`, `EMAIL_FROM`, `APP_BASE_URL`.
- Web: `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` (безопасно наружу, из префикса выводится баннер режима).

## Последовательность

- M6.0 UX-фикс. Быстро, независимо, первым.
- M6.1 Launch-blockers: находки 1, 2, 3, 7, 6, 12, 4, 5, 10, 11. Гейт прода: платящих и реальных пользователей нельзя запускать поверх двойного списания и SSRF.
- M6.2 Биллинг плюс триал: Stripe test-mode, card-first триал, ledger trial-cap, админ-конфиг, counters, анти-абьюз-lite. Зависит от 2 и 7 из M6.1.
- M6.3 Resend: модуль, схема, 4 уведомления, вебхуки, DNS. Зависит от M6.2.
- M6.4 Остаток корректности: находки 8, 9, 13.
