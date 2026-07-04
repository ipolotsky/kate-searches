# 07 — План вехи M1: Ingestion

> Детальный декомпозированный план сбора и подготовки статей. Проектировался с прицелом на то, чтобы ни один пункт будущего роадмапа (M2-M6, фазы 1.5/2/3, мультиязычность) не упирался в блокер, заложенный сейчас. Опорные доки: `03_architecture.md` (стек, адаптеры, cost-metering), `04_mvp_spec.md` §7 (скоуп и acceptance), `05_ai_pipeline_prompts.md` (шов к M2).

## 1. Что делает M1 и критерий готовности

M1 - вертикальный срез конвейера до скоринга: `fetch -> normalize -> novelty -> persist -> extract -> dedup`. На выходе таблица `articles` наполняется чистыми, дедуплицированными, свежими статьями со статусом `extracted`, готовыми к скорингу M2. Плюс синхронный тест источника для UI.

Формальный критерий (AC-1 из `04_mvp_spec.md`):
1. Конвейер не создаёт статьи с `published_at` старше «сегодня» по таймзоне тенанта.
2. Дубли по одному `canonical_url` не создаются дважды.

Скоринг, генерация и UI - вне M1. Но точки их прицепа закладываются сейчас (см. §10).

## 2. Ключевое архитектурное решение: двухфазный конвейер, дедуп по контенту после extract

Один неизменный шов: любой источник -> `Document` -> `articles`, ключ идентичности `(tenant_id, canonical_url)`. Всё специфичное для типа источника (какой курсор, нужен ли JS-рендер, отдаёт ли полный текст, лимит частоты) выносится в декларативные `AdapterCapabilities` и `config_model`. Оркестратор ветвится по флагам capabilities, а не по строке `source.type`.

Порядок стадий (принципиально двухфазный):
1. `fetch -> normalize -> Document`. Тело может быть тонким (sitemap, scraper, короткий RSS).
2. Гейт новизны по `published_at` и таймзоне тенанта. Дешёвый, по дате, не по телу.
3. Upsert в `articles` через `ON CONFLICT (tenant_id, canonical_url) DO NOTHING`, `status='new'`. Это URL-слой дедупа и прямая реализация AC-1: работает по URL, тело не нужно.
4. Стадия extract гидратирует полное тело каскадом `httpx -> Crawl4AI -> Firecrawl`, пересчитывает `content_hash` и `simhash`, двигает статус `new -> extracted` (guard `WHERE status='new'`).
5. Барьер `chord(group(extract_article))(dedup_and_finalize)`. Content-hash-exact, simhash near-dup и кросс-источниковый тай-брейк считаются по финальному телу над уже вставленными строками. Проигравшие помечаются `status='duplicate'` и `duplicate_of`.

Почему дедуп по контенту стоит после extract, а не до persist: `content_hash` и `simhash` тонких тел (sitemap/scraper на момент normalize) ложно совпадают, и дедуп до extract пропустил бы ложные уникальные дубли дальше, заставив M2 платить LLM за одно и то же. Барьер `chord` гарантирует, что дедуп видит финальные тела.

Инварианты надёжности:
1. Persist-then-advance: курсор источника двигается только после успешной записи. При падении и повторе идемпотентный upsert `on conflict` делает at-least-once корректным.
2. Заморозка каноничности: статья, на которую может сослаться `post`, никогда не демоутится в `duplicate`. Поздний высокоприоритетный дубль лишь линкуется, если статус уже `scored`/`drafted`. Иначе - осиротевший пост и сожжённые деньги M2/M3.
3. Провенанс не схлопывается: `article_sources` пишет строку на каждый источник (append), `articles.source_id` держит первый/каноничный. Без этого второй `source_id` перетёр бы первый, и данных для калибровки доверия не осталось бы.
4. Всё под service_role (`engine.py`, роль postgres, bypassrls) - намеренный обход RLS для пайплайна. `tenant_id` всегда берётся из строки `sources`, не из сырья адаптера (защита от кросс-тенант записи под bypassrls). Веб-чтения идут отдельно под authenticated со скоупом RLS.

## 3. Контракт адаптера: эволюционировать один раз, осознанно

Голый `tuple[list[Raw], State]` ломается уже на первом требовании M1: тест источника хочет `limit` и `warnings`, backfill хочет `since` и `mode`. Пока адаптер один (RSS), эволюционировать Protocol и мигрировать RSS в той же задаче дёшево. Позже цена растёт.

Финальный контракт (`services/api/app/adapters/base.py`):

```python
Raw = dict[str, Any]
State = dict[str, Any]  # jsonb-совместимый гибкий курсор

class AdapterCapabilities(BaseModel):
    cursor_kind: Literal["etag", "timestamp", "since_id", "page", "none"]
    supports_incremental: bool
    supports_backfill: bool
    provides_full_text: bool
    needs_javascript: bool
    respects_robots: bool
    emits_media: bool
    default_rate_limit_rpm: int

class FetchRequest(BaseModel):
    source: dict
    state: State
    mode: Literal["incremental", "backfill", "test"] = "incremental"
    limit: int | None = None
    since: datetime | None = None

class FetchStats(BaseModel):
    fetched: int
    new: int
    skipped: int

class FetchResult(BaseModel):
    items: list[Raw]
    state: State
    has_more: bool = False
    warnings: list[str] = Field(default_factory=list)
    stats: FetchStats

class SourceAdapter(Protocol):  # runtime_checkable
    type: str
    capabilities: AdapterCapabilities
    config_model: type[BaseModel]
    def fetch(self, request: FetchRequest) -> FetchResult: ...
    def normalize(self, source: dict, raw: Raw) -> Document: ...
    def validate_config(self, config: dict) -> BaseModel: ...  # дефолт config_model(**config)
```

Типизированные курсоры (`services/api/app/adapters/cursors.py`): `ETagCursor{etag, seen_guids}`, `TimestampCursor{last_published_at}`, `SinceIdCursor{since_id}`, `PageCursor{page, offset}`. Каждый (де)сериализуется в `state`-dict. Адаптер объявляет `cursor_kind` и работает со своим курсором через helper, оркестратор понимает семантику курсора декларативно.

Реестр эволюционирует в `AdapterRegistry` (`services/api/app/adapters/registry.py`): декоратор `@AdapterRegistry.register`, `get(type) -> instance`, `describe() -> list[{type, capabilities, config_schema}]`, где `config_schema = config_model.model_json_schema()`. Это готовое API для M4-формы источника: UI рисует форму из JSON-схемы, ничего не хардкодя. Обратная совместимость: `REGISTRY` сохраняется как алиас, `AdapterRegistry` реализует `__contains__`/`__getitem__`, чтобы существующий `req.type in REGISTRY` из `routes.py` продолжал работать; значения теперь инстансы адаптеров, а не классы.

Про секрет-поля: `describe()` обязан исключать секреты (config помечает их `SecretStr` или `json_schema_extra={"secret": True}`), чтобы токены не текли в UI. Но в M1 ни один источник секретов не несёт (RSS/sitemap/scraper без авторизации, ключ Firecrawl глобальный в config, не per-source), поэтому в M1 это только зафиксированная конвенция-шов: код secret-исключения и обработку `SecretStr` реализуем вместе с первым секрет-несущим источником (соцсети фазы 2), в M1-DoD они не входят.

Изменение `Document` (`services/api/app/models/documents.py`): добавить `body_is_complete: bool = False`. Флаг выставляют адаптеры, отдающие финальное тело (RSS с длинным `content:encoded`, будущие Telegram/Reddit). Стадия extract гидратирует по правилу `not body_is_complete or len(body) < порога` - так extract не дёргает web-fetch по `t.me`/reddit-URL (снимает соцсеть-блокер).

Контент-fetch живёт не в адаптере, а в отдельной абстракции `HtmlFetcher`/`CascadeFetcher` (§5): robots, rate-limit и анти-бот централизованы и переиспользуются и адаптером-скрапером, и стадией extract.

Совместимость RSS: `RssAdapter` получает `capabilities(cursor_kind="etag", provides_full_text=False, emits_media=True, default_rate_limit_rpm=60)`, `config_model=RssConfig(language, full_text_fetch)`. Логика `seen_guids(-5000)` и ETag переезжает под `ETagCursor`. `normalize` меняется точечно: выставляет `body_is_complete` (есть ли длинный `content:encoded`) и `metadata.dateless` при отсутствии `pubDate` (см. §6). Ключевое: `body_is_complete` живёт только в pydantic-`Document` и не переживает persist, поэтому `upsert_document` кладёт его в `articles.metadata`, а стадия extract читает его оттуда (иначе флаг теряется между фазами и extract вынужден падать на length-эвристику, которую §5 запрещает для соцсетей). Соцсети фазы 2 и OAuth фазы 3 - тот же Protocol, свой `config_model` с секрет-полями, свой `cursor_kind`. Ядро (оркестратор, персистентность, дедуп, тест источника) не трогается.

## 4. Оркестрация (Celery)

`celery[redis]>=5.4` уже в зависимостях, кода нет. Создаём `services/api/app/worker/celery_app.py`: broker и **result backend** на redis (backend включён с M1 - нужен для `chord`-барьера уже сейчас и для chaining M2/M3), `result_expires` поднят под длинные прогоны, `task_acks_late=True`, `task_reject_on_worker_lost=True`, `worker_prefetch_multiplier=1`, очереди `default`/`fetch`/`extract` с роутингом по имени задачи, timezone UTC.

Топология (`services/api/app/worker/tasks.py`), линейный DAG с fan-out/fan-in и барьером:

1. `dispatch_due_tenants` - heartbeat beat каждые 15 минут. Celery beat не умеет per-tenant tz-cron нативно, поэтому: для каждого enabled-тенанта локальное время через `zoneinfo(tenants.timezone)`, и если локальный час равен `tenants.pipeline_hour_local` - атомарный `INSERT INTO pipeline_runs ... ON CONFLICT (tenant_id, run_date, mode) DO NOTHING RETURNING id`. Критично: `run_date` вычисляется как **локальная дата тенанта** в `zoneinfo(tenants.timezone)` на момент диспатча, не UTC-дата - иначе для тенантов с большим оффсетом ключ идемпотентности разъедется с tz-расписанием (два прогона за одни локальные сутки или блок легитимного); покрыть тестом на UTC-границе суток. Enqueue `run_tenant_pipeline` только при реальной вставке (защита от двойного диспатча при перекрытии тиков и рестартах). Диспатч выбирает due-**источники** (`enabled AND (next_run_at IS NULL OR next_run_at <= now)`), а не только весь тенант, и проставляет `next_run_at` - это хук под per-source cadence, но НЕ полная разблокировка: дневной ключ `unique(tenant_id, run_date, mode)` допускает один incremental-прогон в сутки, поэтому суб-дневная per-source частота фазы 2 потребует локально расширить ключ идемпотентности (слот/окно в `run_date` или отдельный per-source леджер) - точечная правка диспатча, не рефактор ядра. В M1 дневной tenant-run - единственная политика.
2. `run_tenant_pipeline(tenant_id, run_id, mode, since)` - грузит due-источники, строит `chord(group(ingest_source.s(source_id, run_id, mode, since) для каждого))(finalize_fetch.s(tenant_id, run_id))`. Один упавший источник не роняет остальные (partial-run).
3. `ingest_source` - идемпотентная единица: `throttle.acquire(host, rpm)` и robots -> `adapter.fetch(FetchRequest)` в цикле по `has_more` с потолком `max_pages`/`max_items` -> `normalize` -> гейт новизны -> upsert `ON CONFLICT DO NOTHING` (`status='new'`) -> **после** персистентности продвинуть `sources.state` и `last_run_at` -> записать провенанс в `article_sources` -> вернуть id новых статей. Ретраи: `autoretry_for=(TransientFetchError,)`, `retry_backoff=True`, `retry_backoff_max=600`, `retry_jitter=True`, `max_retries=5`. HTTP 429 - `self.retry(countdown=Retry-After)`. Перманентные ошибки (404, robots-deny, parse) не ретраятся, пишутся в `sources.last_status`/`last_error`.
4. `finalize_fetch` -> **барьер** `chord(group(extract_article.s(id) для новых))(dedup_and_finalize.s(tenant_id, run_id))`. Guard пустого прогона: если новых id нет (все дубли по URL или всё отсеяно новизной - типичный день), не строить пустой `chord` (в Celery это version-dependent edge: callback может не выстрелить, и `pipeline_runs` навсегда зависнет в `running`), а звать `dedup_and_finalize` напрямую. Финализацию прогона (`pipeline_runs.status`, health, stats) делает именно `dedup_and_finalize`, а не внешний `chord(ingest_source)`: внешний барьер завершения extract+dedup не гарантирует, потому что вложенный `chord` декуплит финализацию.
5. `extract_article` - гидратация тела `CascadeFetcher`, trafilatura, язык, медиа, пересчёт `content_hash`+`simhash`, `new -> extracted` (guard `WHERE status='new'`, идемпотентно, без повторного платного fetch). На каждый **платный** fetch (Firecrawl/BrightData) - строка `ai_usage(stage='extract', model='firecrawl'/..., cost_usd=оценка, pipeline_run_id)`. Единственное место учёта COGS скрапинга, ретроактивно невосстановимо.
6. `dedup_and_finalize` - дедуп по финальному телу (§6), проигравшие в `duplicate` при статусе `in (new, extracted)`, типизированные счётчики в `pipeline_runs`, обновление здоровья источников. Здесь же точка прицепа M2: `score_article` вешается group-ом с гейтом по `status='extracted'`.

Rate-limit и robots декларативны и переиспользуемы: Redis token-bucket per host (общий для всех тенантов, `rpm` из capabilities/config), robots.txt в Redis с TTL, identifiable UA из settings. Backfill и incremental - одна топология: `run_tenant_pipeline(mode='backfill', since=...)` снимает today-гейт и включает пагинацию по `has_more`, нового кода оркестрации не нужно.

Вердикт по dlt: **не берём в M1**. Инкрементальность и state уже свои (`sources.state` + типизированные курсоры), dlt принёс бы второй конкурирующий state-механизм и свои `_dlt_*` таблицы мимо `unique(tenant_id, canonical_url)`. Целевая запись - идемпотентный upsert в одну таблицу под service_role, плохо ложится на dlt-раннеры. Конвейер transform-тяжёлый (extract, дальше LLM), а не ELT. Дверь открыта: конкретный высоковолюмный источник может использовать dlt внутри своего адаптера, ядро не узнает. Scrapy тоже не берём: sitemap - парс XML, scraper - одностраничный fetch плюс extract, краул-фронтир не нужен. Пересмотр - только при вале высокообъёмных API-источников со сложной пагинацией, не в ближайшие две вехи.

## 5. Экстракция

Extract - отдельная не-LLM стадия (LLM-обогащение `ExtractedArticle` объединено со скорингом в M2, см. `05_ai_pipeline_prompts.md`). Цель: чистое полное тело в markdown, язык, медиа.

trafilatura (уже в deps): `extract(html, output_format="markdown", with_metadata=True, favor_precision=True, include_tables=True)` -> тело плюс author/date/language/image. Одна точка trafilatura, переиспользуется RSS-гидратацией, sitemap- и scraper-адаптерами. Язык: `metadata.language`, fallback `source.config.language`, иначе `None`.

Каскад скрапера как переиспользуемая абстракция `HtmlFetcher` (`services/api/app/fetch/`): Protocol `fetch_html(url, render_js, timeout) -> FetchedPage{html, status, final_url, from_cache}`. Реализации: `HttpxFetcher` (дефолт, дёшево, без JS) -> `Crawl4aiFetcher` (JS-рендер, за extra `[scraper]` и `capabilities.needs_javascript`) -> `FirecrawlFetcher` (fallback по API, `FIRECRAWL_API_KEY` уже в config) -> BrightData/Zyte (анти-бот, отложенный слот). `CascadeFetcher` эскалирует дёшево-дорого по **качеству** извлечения (пустое/тонкое тело, анти-бот сигнал), а не заранее. Один `CascadeFetcher` переиспользуют scraper-адаптер (в fetch) и стадия extract (дотяжка RSS/sitemap).

Политика полного тела: гидратировать если `not body_is_complete or len(body) < порога` (около 500-600 символов). `body_is_complete` выставляет адаптер, а не эвристика длины - иначе соцсети фазы 2 (короткое авторитетное тело) ложно уходят на web-fetch. Стадия extract работает со строкой `articles` по id, поэтому `body_is_complete` читается из `articles.metadata` (куда его положил `upsert_document`), а не из in-memory `Document`. Если извлечение упало (paywall, анти-бот) - деградировать на RSS-summary как тело, `metadata.extraction_failed=true`, статус остаётся `new` (строку не теряем). `content_hash` пересчитывается по финальному телу.

Этика (`03_architecture.md` §8): robots.txt до fetch (`capabilities.respects_robots`), identifiable UA из settings, per-host throttle, crawl-delay. Тело - для внутреннего пайплайна, выход M3 трансформирует, а не копирует.

Учёт стоимости: на каждый платный fetch - строка `ai_usage(stage='extract', model=провайдер, cost_usd=оценка кредита, pipeline_run_id)`. `stage='extract'` уже в check-констрейнте `ai_usage` из `0001` - миграция для этого не нужна.

## 6. Дедуп и новизна

Новизна (AC-1): добавить `is_novel(published_at, tenant_timezone, now_utc=None, lookback_hours=0, mode="incremental", since=None)` - граница есть полночь сегодняшнего дня в `zoneinfo(tenant_timezone)`, приведённая к UTC, минус lookback-грейс. В `mode="backfill"` граница есть `since` (без today-гейта), иначе backfill пилота молча выкинул бы всё старше полуночи. Per-source override `novelty_days` через `source.config`. Функцию `is_fresh` оставить для обратной совместимости (существующие тесты не трогаем), оркестратор использует `is_novel`. `tenants.timezone` валидировать через `zoneinfo` при записи с fallback UTC, покрыть тестом на границе суток и DST.

Статьи без даты - отдельный gap AC-1: сейчас `_parse_date` (`rss.py:67`) молча возвращает `now()`, из-за чего статья без `pubDate` ложно проходит гейт новизны как «сегодняшняя» и создаётся - прямое нарушение AC-1 п.1. Правка (входит в T3, значит RSS-normalize меняется точечно): `_parse_date` сигналит отсутствие даты (`None`), `normalize` выставляет `metadata.dateless=true`, и dateless-статья гейт новизны НЕ проходит (продуктовое правило: без достоверной даты в дневное окно не берём), а не проходит его фиктивно. Флаг остаётся для наблюдаемости.

Дедуп - слоёный каскад, весь **до** скоринга, оформлен списком `DedupStrategy` (окно и скан - параметр стратегии, не хардкод «дневное», чтобы pgvector-слой фазы 2 встал без правки границ):
1. URL-канон (готово, `canonicalize_url`) -> `canonical_url` плюс DB-гарантия `unique(tenant_id, canonical_url)` плюс upsert `ON CONFLICT DO NOTHING`. Закрывает AC-1 по URL.
2. Content-hash-exact (`sha256` нормализованного тела) - синдикация под разными URL. Считается **после** extract по финальному телу, не на момент normalize. Поиск по `idx_articles_content_hash(tenant_id, content_hash)`.
3. Simhash near-dup: собственная `simhash64(text) -> int` плюс `hamming` (около 15 строк, чистая функция, **без** datasketch - он про MinHash/LSH под Jaccard, а колонка `simhash bigint` это 64-битный SimHash-отпечаток). Знаковость: unsigned 64-бит и signed bigint связаны через `value - 2**63`, обязателен round-trip тест. `hamming <= 3` линейным сканом по дневному окну (`idx_articles_published`). LSH/pgvector - фаза 2.
4. Кросс-источниковый тай-брейк: одна история из нескольких источников - каноничной оставить строку источника с бОльшим `priority` (шкала higher=trusted, зафиксировать в схеме, доках и коде; сверить с конвенцией доков Kate до M6), при равенстве - более раннее `published_at`. Проигравший -> `status='duplicate'` плюс `duplicate_of` (soft, обратимо, не hard-delete). Инвариант: не демоутить `scored`/`drafted`. Провенанс дедупа в `articles.metadata {dedup_method, matched_article_id, distance}`.

Мультиисточниковая провенансность: `article_sources(article_id, source_id, external_id, priority_at_seen, first_seen_at, unique(article_id, source_id))` пишет строку на каждый источник (append, не overwrite). На этом стоят priority-тай-брейк дедупа, M5-аналитика источников и M6-калибровка доверия.

Переиздания и обновления: тот же `canonical_url` с изменившимся `content_hash` - апдейт, не дубль. Политика upsert: всегда `fetched_at`; если `content_hash` изменился и статус `in (new, extracted, filtered_out)` - обновить тело/хеш и вернуть на переоценку; если `scored`/`drafted` - тело не затирать (не переплачивать за M2/M3), новый хеш в `metadata`.

## 7. Персистентность и схема

Всё под service_role. `tenant_id` всегда из строки `sources`, не из сырья адаптера. Веб-чтения идут отдельно под authenticated со скоупом RLS.

Репозитории (`services/api/app/db/repositories.py`, дополняем существующий `insert_ai_usage`):
- `ArticleRepository`: `upsert_document(session, doc) -> (article, inserted)` через `postgresql.insert(...).on_conflict_do_nothing(index_elements=[tenant_id, canonical_url]).returning(id)` - `id is not None` значит новая строка (в очередь на extract), `None` значит дубль по URL. Условное обновление тела при переиздании - отдельный путь с guard по статусу. `find_by_content_hash`, `find_near_duplicate(simhash, window)`, `mark_duplicate(article_id, duplicate_of, method)` с guard не-`scored`/`drafted`, `upsert_article_source`.
- `SourceRepository`: `get_due_sources`, `advance_state(source_id, new_state, last_run_at)`, `set_health(last_status, last_error)`.
- `PipelineRunRepository`: `claim_run` (atomic insert), `finalize(run_id, counters, status)`.

Одна `session_scope` на источник, батч-upsert, state не продвигать при провале fetch.

Машина статусов M1: `new` (заингещено, тело из источника) -> `extracted` (тело дотянуто) -> ветка `duplicate` (near/exact-дубль плюс `duplicate_of`). Дальше M2: `scored`/`filtered_out`, M3: `drafted`.

ORM (`services/api/app/db/models.py`) синхронизировать 1:1. Критично: колонку `articles.metadata` мапить как `doc_metadata = mapped_column("metadata", JSONB, ...)` - атрибут `.metadata` зарезервирован `DeclarativeBase` (`Base.metadata`), иначе импорт модели падает. Обновить `test_db_models.EXPECTED_TABLES` (добавить `article_sources`, `pipeline_runs`, `source_secrets`).

Миграция `supabase/migrations/0002_ingestion.sql` - строго аддитивная поверх `0001`, `if-not-exists`, RLS на каждую новую таблицу с `tenant_id`. Секреты будущих OAuth/токенов не в `sources.config` (читается authenticated под RLS), а в отдельной `source_secrets`, service_role-only. `pipeline_runs` и `article_sources` read-only для authenticated (леджер и провенанс пишет пайплайн под service_role, клиент только читает свой скоуп - иначе участник тенанта мог бы править провенанс, которым калибруется доверие источников). `source_secrets` в M1 - только DDL-шов (пустая service_role-only таблица под OAuth-токены фаз 2/3), кода записи/чтения в M1 нет. `ai_usage.pipeline_run_id` и `articles.last_pipeline_run_id` связывают метеринг и выход с прогоном (M5-репорты, учёт backfill, Stripe фазы 1.5).

```sql
-- articles: metadata (Document.metadata негде хранить) + дедуп-линковка + атрибуция прогона
alter table articles add column if not exists metadata jsonb not null default '{}'::jsonb;
alter table articles add column if not exists duplicate_of uuid references articles(id) on delete set null;
alter table articles add column if not exists last_pipeline_run_id uuid;
alter table articles drop constraint if exists articles_status_check;
alter table articles add constraint articles_status_check
  check (status in ('new','extracted','filtered_out','scored','drafted','duplicate'));
create index if not exists idx_articles_content_hash on articles(tenant_id, content_hash);

-- sources: здоровье + хук per-source cadence
alter table sources add column if not exists last_status text;
alter table sources add column if not exists last_error text;
alter table sources add column if not exists last_error_at timestamptz;
alter table sources add column if not exists next_run_at timestamptz;

-- tenants: локальный час дневного прогона для tz-диспетчера
alter table tenants add column if not exists pipeline_hour_local smallint not null default 6;

-- ai_usage: атрибуция стоимости (в т.ч. платного скрапинга) к прогону
alter table ai_usage add column if not exists pipeline_run_id uuid;

-- мультиисточниковая провенансность (M5-аналитика, M6-калибровка, priority-тай-брейк)
create table if not exists article_sources (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  article_id uuid not null references articles(id) on delete cascade,
  source_id uuid references sources(id) on delete set null,
  external_id text,
  priority_at_seen int,
  first_seen_at timestamptz not null default now(),
  unique (article_id, source_id)
);
create index if not exists idx_article_sources_tenant on article_sources(tenant_id, source_id);

-- леджер прогонов: идемпотентный диспатч + наблюдаемость + M5-репорты
create table if not exists pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references tenants(id) on delete cascade,
  run_date date not null,
  mode text not null default 'incremental' check (mode in ('incremental','backfill')),
  status text not null default 'running' check (status in ('running','success','partial','failed')),
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  fetched int not null default 0,
  new int not null default 0,
  duplicated int not null default 0,
  extracted int not null default 0,
  failed int not null default 0,
  stats jsonb not null default '{}'::jsonb,
  unique (tenant_id, run_date, mode)
);
create index if not exists idx_pipeline_runs_tenant on pipeline_runs(tenant_id, run_date desc);

-- секреты источников: service_role-only, никогда не видны authenticated (OAuth/токены фаз 2/3)
create table if not exists source_secrets (
  source_id uuid primary key references sources(id) on delete cascade,
  tenant_id uuid not null references tenants(id) on delete cascade,
  secrets jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

-- RLS
alter table article_sources enable row level security;
alter table pipeline_runs enable row level security;
alter table source_secrets enable row level security;
drop policy if exists article_sources_isolation on article_sources;
drop policy if exists article_sources_select on article_sources;
create policy article_sources_select on article_sources
  for select using (tenant_id = current_tenant_id());
drop policy if exists pipeline_runs_select on pipeline_runs;
create policy pipeline_runs_select on pipeline_runs
  for select using (tenant_id = current_tenant_id());
-- source_secrets: политик для authenticated нет => доступа к строкам нет; service_role обходит RLS.

-- гранты: default privileges из 0001 уже выдали authenticated CRUD на новые таблицы - ужесточаем
revoke insert, update, delete on article_sources from authenticated;       -- провенанс пишет пайплайн (service_role), клиент читает
revoke insert, update, delete on pipeline_runs from authenticated;         -- read-only леджер
revoke select, insert, update, delete on source_secrets from authenticated; -- полностью скрыто
```

Замечание про default privileges: в `0001` есть `alter default privileges ... grant ... to authenticated`, поэтому новые таблицы автоматически получают CRUD, и его нужно явно `revoke` для control-таблиц (сделано выше). Это ровно тот follow-up, что отмечен в HANDOFF: при желании поменять дефолт на `grant select` в отдельной задаче до 0002.

Зависимости: не добавлять `datasketch` (свой `simhash64`), не добавлять `dlt`/`Scrapy`. Добавить `lxml` (sitemap) и явный `httpx` (fetcher). `crawl4ai` - в optional-extra `[scraper]` (playwright тяжёлый, идёт за extra и `capabilities.needs_javascript`, дефолт extract остаётся `httpx`+trafilatura, чтобы `make test` был лёгким).

## 8. Тест источника

`POST /internal/sources/test` - синхронный dry-run адаптера, без единой записи в БД, без фиксации state, без очереди (сейчас заглушка возвращает лишь `{type, supported, url}`). UI при добавлении источника нужен моментальный ответ, не Celery.

Вход: `{type, url, config?, tenant_id?}` (`tenant_id` для tz, UA, `is_novel`). Шаги:
1. `type in AdapterRegistry`, иначе `{ok: false, error: "unsupported_type", supported_types: [...]}`.
2. `adapter.validate_config(config)` - ошибки Pydantic структурно как `invalid_config` с полями.
3. `adapter.fetch(FetchRequest(source={url, config, tenant_id, id: None}, state={}, mode="test", limit=5))` с жёстким таймаутом около 10-15 секунд через `run_in_threadpool` (fetch блокирующий).
4. `normalize` первых пяти, для scraper/sitemap - один sample-предпросмотр тела через `httpx`+trafilatura.

Firecrawl/BrightData в тесте запрещены - не жечь деньги. Ответ в UI: `{ok, supported, capabilities, cursor_kind, stats, warnings, sample:[{title, url, canonical_url, published_at, is_novel, language, has_body, body_preview}], error?}`. `is_novel` считается по tz тенанта - маркетолог сразу видит, попадут ли элементы в дневное окно. Коды ошибок: `unsupported_type`, `invalid_config`, `fetch_timeout`, `robots_disallowed`, `parse_error`, `empty_feed`. Эндпоинт остаётся в FastAPI, ничего не пишет в `articles`/`sources`/`state`, заодно валидирует новый адаптер при добавлении (EPIC A4).

## 9. Декомпозиция задач

15 задач. Размер: S - до полудня, M - день-полтора, L - два-три дня. Зависимости в скобках.

| # | Задача | Размер | Зависит от |
|---|--------|--------|-----------|
| T1 | Эволюция `SourceAdapter` Protocol + типизированные курсоры + `Document.body_is_complete` | M | - |
| T2 | `AdapterRegistry` с `register` и `describe()` | S | T1 |
| T3 | Миграция `RssAdapter` на новый контракт | S | T1, T2 |
| T4 | Sitemap-адаптер (news-sitemap + sitemap-index) | M | T1, T2 |
| T5 | `HtmlFetcher` + `CascadeFetcher` + robots + per-host token-bucket | M | T1 |
| T6 | Scraper-адаптер через `CascadeFetcher` | M | T4, T5 |
| T7 | Стадия extract | M | T5, T1 |
| T8 | Дедуп-каскад + tz-aware новизна | M | T1 |
| T9 | Миграция `0002` + ORM sync | M | - |
| T10 | Репозитории персистентности | M | T9 |
| T11 | Celery-приложение + очереди + result backend | S | - |
| T12 | Топология задач ingestion | L | T3, T4, T6, T7, T8, T10, T11 |
| T13 | Провод эндпоинтов (`/pipeline/run`, `/sources/test`) | M | T2, T7, T8, T12 |
| T14 | Зависимости, конфиг, инфра (compose worker+beat) | S | T11, T12 |
| T15 | E2E acceptance AC-1 | S | T10, T12 |

Детализация ключевых задач:

**T1. Контракт адаптера.** Файлы: `adapters/base.py`, `adapters/cursors.py`, `models/documents.py`. Ввести `AdapterCapabilities`/`FetchRequest`/`FetchResult`/`FetchStats`, обновить Protocol, типизированные курсоры с (де)сериализацией в dict, `Document.body_is_complete`. Acceptance: `runtime_checkable` сохранён, модели валидируются, курсоры round-trip в dict. Тесты: валидация моделей, round-trip курсоров, `isinstance`-проверка Protocol на заглушке.

**T5. Fetcher и троттлинг.** Файлы: `fetch/base.py`, `fetch/httpx_fetcher.py`, `fetch/cascade.py`, `fetch/crawl4ai_fetcher.py`, `fetch/firecrawl_fetcher.py`, `worker/throttle.py`, `worker/robots.py`. `CascadeFetcher` эскалирует по качеству, `throttle.acquire(host, rpm)` token-bucket на Redis, robots-кэш с TTL, Crawl4AI ленивым импортом за extra. Acceptance: каскад переходит к следующему при пустом/ошибочном результате, robots-deny блокирует, token-bucket ограничивает частоту, `make test` не требует playwright. Тесты: каскад падений, robots allow/deny, token-bucket на фейковых часах.

**T8. Дедуп и новизна.** Файл: `pipeline/dedup.py`. `is_novel` по календарной tz (+backfill `since`), `simhash64`/`hamming` со signed-bigint маппингом, content-hash-exact, кросс-источниковый priority-тай-брейк, список `DedupStrategy`. Acceptance: AC-1 (старьё по tz не проходит, backfill пропускает старое по `since`), near-dup ловится на перефраз, не на разные тексты, priority-победитель верный. Тесты: граница суток и DST, simhash round-trip signed-unsigned на граничных битах, порог Hamming, кросс-источник по priority, dateless-флаг.

**T12. Топология (ядро вехи).** Файлы: `worker/tasks.py`, `worker/schedule.py`. `dispatch_due_tenants` (tz + идемпотентность через `pipeline_runs` + due-источники), `run_tenant_pipeline` (chord), `ingest_source` (persist-then-advance, ретраи), `finalize_fetch` -> барьер `chord(extract)` -> `dedup_and_finalize` (post-extract дедуп, stats, health, M2-seam). Acceptance: полный прогон на моках дедуплицирует по финальному телу и не создаёт старьё, повторный dispatch того же дня не создаёт второй run, ретрай на transient и no-retry на `robots_disallowed`, барьер соблюдён. Тесты (eager + БД): E2E прогон, гашение двойного dispatch, extract завершается до dedup.

**T15. Acceptance AC-1.** Файл: `tests/integration/test_ingestion_ac1.py`. Фейк-адаптер отдаёт свежую, вчерашнюю и дубль из разных источников, прогон создаёт только свежую уникальную, повтор не плодит, кросс-источниковый дубль схлопывается после extract. Acceptance: ровно одна строка на свежий уникальный `canonical_url`, статья старше cutoff по tz не создана, повтор даёт 0 новых, проигравший дубль есть `duplicate` плюс `duplicate_of`, `article_sources` содержит оба источника.

Остальные задачи (T2, T3, T4, T6, T7, T9, T10, T11, T13, T14) - по той же структуре: цель, файлы, интерфейсы, acceptance, тесты. Полная карта выше в таблице зависимостей.

## 10. Матрица расширяемости: почему роадмап не заблокирован

| Пункт роадмапа | Чем M1 его не блокирует |
|---|---|
| M2 скоринг | `dedup_and_finalize` - точка прицепа: `score_article` вешается group-ом на post-extract барьер, гейт `status='extracted'`. Дедуп по контенту уже прошёл, M2 не платит LLM за дубли. `ai_usage(stage='score', pipeline_run_id)` готов. |
| M3 генерация | `Document`/`articles` - стабильный шов. `posts.article_id` ссылается на статью, которая не демоутится в `duplicate` (заморозка каноничности), пост не осиротеет. `brand_profiles` уже в схеме. |
| M4 UI источника | `AdapterRegistry.describe()` отдаёт `config_schema` + capabilities: форма источника рисуется динамически, без хардкода, секрет-поля исключены. `/internal/sources/test` - готовый синхронный dry-run с sample/is_novel/warnings. |
| M5 админка/репорты | `pipeline_runs` с типизированными счётчиками + `ai_usage.pipeline_run_id` + `articles.last_pipeline_run_id`: стоимость и выход атрибутируются к прогону, backfill отделён от дневного. `article_sources` даёт отчёт по источникам. |
| M6 пилот LOOTON | `mode='backfill'` + `since` на той же топологии, гейт новизны использует `since`. `article_sources` + priority-тай-брейк дают данные для калибровки доверия источников. |
| Фаза 1.5 Stripe | Весь COGS учтён per-tenant per-run: LLM через `ai_usage(stage=score/draft)`, платный скрапинг через `ai_usage(stage='extract')`. Stripe читает `ai_usage`/`pipeline_runs`, ничего не собирается задним числом. |
| Фаза 2 соцсети | Тот же Protocol: `cursor_kind='since_id'`, свой `config_model`, `body_is_complete=True` (extract не дёргает web-fetch по `t.me`). Секреты в `source_secrets`. Ядро не трогается. |
| Фаза 2 pgvector-дедуп | Список `DedupStrategy`: embedding-стратегия добавляется в конец каскада, окно/скан - параметр стратегии. `duplicate_of`-линковка уже в схеме. `articles.embedding` - дешёвая аддитивная миграция позже. |
| Фаза 2 автопубликация | `posts` как терминальный артефакт уже отвязан от ingestion. Провенанс (`article_sources`) и JSON-LD дают всё для публикации. Ingestion-ядро не участвует. |
| Фаза 3 OAuth-соцсети | `source_secrets` (service_role-only, revoke у authenticated): OAuth-токены вне `config`, не текут под RLS. `describe()` исключает секрет-поля. Конвенция зафиксирована в M1. |
| Per-source cadence | `sources.next_run_at` + диспатч по due-источникам - хук готов. Суб-дневная частота потребует расширить ключ идемпотентности `pipeline_runs` слотом/окном (точечная правка диспатча), не рефактор ядра. |
| Мультиязычность ru+en | `articles.language` детектится в extract и хранится, `brand_profiles.locales` уже есть. Новый язык есть поле, не код. |

## 11. Риски и митигации

| Риск | Митигация |
|---|---|
| Celery beat не умеет per-tenant tz-cron, heartbeat может дать двойной диспатч | Атомарный INSERT в `pipeline_runs` с `unique(tenant_id, run_date, mode)` ON CONFLICT DO NOTHING RETURNING, enqueue только при вставке |
| `content_hash`/`simhash` по тонкому телу на момент normalize - ложные дубли | Дедуп по контенту вынесен в post-extract барьер, хеши по финальному телу |
| Поздний дубль демоутит `scored`/`drafted` - осиротевший пост, сожжённые деньги | Инвариант: `mark_duplicate` только при `status in (new, extracted)`, каноничность замораживается |
| RSS без `pubDate` -> `_parse_date` даёт `now()` -> ложная свежесть, создание статьи (нарушение AC-1) | `_parse_date` возвращает `None`, `normalize` ставит `metadata.dateless=true`, dateless-статья гейт новизны не проходит (в дневное окно не берём) |
| Пустой `chord`-header при нуле новых статей - callback может не выстрелить, `pipeline_runs` зависает в `running` | Guard: при пустом списке новых id звать `dedup_and_finalize` напрямую, минуя `chord`; eager-тест на прогон с нулём новых |
| simhash unsigned 64-бит vs signed bigint - переполнение, сломанный Hamming | Явная упаковка `value - 2**63` на записи/чтении + round-trip тест на граничных битах |
| Crawl4AI/playwright тяжёлый, Firecrawl/BrightData стоят денег | Crawl4AI за extra `[scraper]` + `needs_javascript`, дефолт `httpx`+trafilatura, каскад по сигналу неудачи, BrightData запрещён в dry-run |
| Fan-out extract - N исходящих запросов в день -> IP-баны | Redis token-bucket per host, robots-кэш, identifiable UA, эскалация каскада, crawl-delay |
| Секреты OAuth/токенов в `sources.config` - утечка под RLS | `source_secrets` service_role-only, `describe()` исключает секрет-поля |
| Стоимость платного скрапинга не учтена - M5/Stripe слепы, ретроактивно невосстановимо | `ai_usage(stage='extract', cost_usd, pipeline_run_id)` на каждый платный fetch |
| Продвижение курсора раньше персистентности теряет элементы при сбое | Строгий persist-then-advance, идемпотентный upsert как страховка |
| `articles.metadata` коллидирует с `DeclarativeBase.metadata` - импорт ORM падает | Мапить как `doc_metadata = mapped_column("metadata", JSONB, ...)` |
| Некорректная/DST tz тенанта ломает границу «сегодня» и диспатчер | Валидация `timezone` через `zoneinfo` при записи + fallback UTC, тесты на границе суток и DST |
| Кросс-источниковый near-dup линейным сканом O(n^2) при росте потока | Для MVP-объёмов дневного окна дёшево, окно/скан - параметр `DedupStrategy`, переход на LSH/pgvector в фазе 2 |
| `chord` требует result backend, без него барьер не соберётся | Redis result backend включён с M1, `result_expires` поднят, eager-тест на сборку chord |

## 12. Открытые вопросы (решить до/во время реализации)

1. Направление шкалы `priority` (1..5): принято higher=trusted, но сверить с реальной конвенцией доков Kate до M6, иначе кросс-источниковый победитель инвертируется и калибровка искажается.
2. Продуктовое правило кросс-локального дубля: один инфоповод в ru- и en-источнике - это один черновик или два? Влияет на границы дедупа и на pgvector фазы 2, решить до генерации M3.
3. Оценка стоимости платного fetch (Firecrawl-кредит -> `cost_usd`): фиксированная ставка за вызов или тариф по объёму? Нужна для точности M5/Stripe.
4. Порог «тонкого тела» для гидратации (около 500-600 символов) и порог Hamming near-dup (`<= 3`) - подобрать на реальных источниках LOOTON в M6.
5. Дефолтная политика robots при недоступном/5xx `robots.txt`: fail-open с троттлингом (фиды) против консервативного (scraper) - зафиксировать поведение.
6. Частота heartbeat диспатчера (15 минут) против риска пропуска прогона при простое воркера: нужен ли ручной re-run как страховка или catch-up-логика в dispatch.
7. Отдельная колонка `articles.embedding` + pgvector уже в `0002` (дешёвая заготовка) или строго в фазе 2 - решить, чтобы не делать вторую миграцию окна дедупа.

## 13. Порядок выполнения (волны по зависимостям)

Волны параллелятся между двумя инженерами. Внутри волны задачи независимы.

1. Волна 0 (можно начинать сразу): **T1** (контракт), **T9** (миграция + ORM), **T11** (Celery-app).
2. Волна 1: **T2** (реестр), **T5** (fetcher/троттлинг), **T8** (дедуп/новизна), **T10** (репозитории).
3. Волна 2: **T3** (RSS на новый контракт), **T4** (sitemap), **T7** (extract).
4. Волна 3: **T6** (scraper).
5. Волна 4: **T12** (топология - ядро, сходятся все ветки).
6. Волна 5: **T13** (эндпоинты), **T14** (инфра/compose), **T15** (E2E AC-1).

Оценка совпадает с ориентиром `04_mvp_spec.md` §7 для M1 (1.5-2 недели на 1-2 инженеров): критический путь T1 -> T5 -> T7 -> T12 -> T15.

## 14. Definition of Done вехи

1. `make lint` и `make test` зелёные без тяжёлых extra (playwright не требуется для unit).
2. Интеграционный `test_ingestion_ac1` доказывает AC-1 (свежесть по tz, дедуп по URL/контенту, идемпотентность повтора, провенанс двух источников); отдельный eager-тест: прогон с нулём новых статей финализирует `pipeline_runs` (не зависает в `running`); тест на dateless-статью (не создаётся).
3. `worker` и `beat` стартуют в `docker-compose` (smoke).
4. Тест источника из UI-контракта возвращает sample без записи в БД.
5. Каждый платный fetch пишет строку в `ai_usage(stage='extract')`.
6. Миграция `0002` применяется поверх `0001` идемпотентно, control-таблицы (`pipeline_runs`, `source_secrets`) недоступны на запись/чтение authenticated (проверяется integration-тестом RLS в стиле существующего `test_rls`).
