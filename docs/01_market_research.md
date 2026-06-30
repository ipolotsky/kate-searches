# 01 — Рыночный и технический ресёрч

Данные собраны живым веб-поиском, июнь 2026. Цены проверены по карточкам вендоров/обзорам на момент сбора. Категории AEO и autopilot-генерации меняют цены часто — перепроверять перед внешним использованием.

---

## 1. Конкурентный ландшафт

### 1.1 Главный вывод

Рынок расколот надвое, и наш продукт — мост между половинами:

- **Мониторинг/листенинг** (Feedly, Brand24, Meltwater, BuzzSumo, Profound, Otterly) — умеют ловить новости и сигналы, но **не пишут ни строчки**.
- **SEO-автопилоты** (RankYak, Byword, SEObot, Cuppa) — генерят посты пачками, но **по ключевым словам, а не по новостям**, и без релевантности под бренд.

Буквальный конвейер «следить за новостями → понять, важна ли новость **именно этой аудитории** → написать черновик, привязанный к продукту и упакованный под AEO → дать на ревью в дашборде» **не упакован ни одним крупным горизонтальным игроком**.

### 1.2 Прямые и близкие конкуренты

| Продукт | Категория | Новость как триггер | Релевантность под аудиторию | Полный SEO/AEO-черновик | Дашборд черновиков | Цена ($/мес) |
|---|---|---|---|---|---|---|
| **AIBlogMax** | Прямой конкурент | ✅ | Частично (keyword incl/excl) | ✅ (SEO, без AEO) | ✅ | ~$19/$50/$75 |
| **Arvow** (ex-Journalist AI) | Автопилот, news-capable | ✅ (один из входов) | ❌ (keyword) | ✅ | Частично | $39/$69/$249 |
| **GrackerAI** | Вертикальный news→AEO | ✅ | Вертикально (только кибербез) | ✅ (AEO) | Частично | Free/~$79/~$199 |
| **OGTool** | AEO generate+publish | Блоги конкурентов, не новости | Частично | ✅ (AEO) | ✅ | от $99; managed $6–8k |
| **RankYak** | Keyword-автопилот | ❌ (поисковый спрос) | ❌ | ✅ | Частично | $99 flat |
| **Byword** | Programmatic SEO | ❌ (CSV) | ❌ | ✅ | Bulk-очередь | $99/$299/$999 |
| **Feedly + Leo AI** | Мониторинг новостей | ✅ (сильный) | ✅ (**лучший на рынке фильтр**) | ❌ | Лента, не черновики | ~$8–13 |
| **Frase** | Content OS (SEO+GEO) | ❌ (вопросы на сайте) | ✅ (вопросы посетителей) | ✅ | ✅ (с лимитом) | $39/$103/$239 |
| **Writesonic / Surfer / Jasper** | Writer→GEO платформы | ❌ | Частично | ✅ | Частично | $49–399 |
| **Profound / Otterly / Peec** | AEO-мониторинг | ❌ | ❌ | ❌ (только рекомендации) | ❌ | $29–989 |
| **Brand24 / Meltwater / BuzzSumo** | Листенинг/медиаинтеллидженс | ✅ | Частично | ❌ | ❌ | $199–100k+/год |

Полная таблица из 25+ продуктов — в исходном ресёрче; здесь только значимые для позиционирования.

### 1.3 Кого реально стоит опасаться

**AIBlogMax** — единственный, кто делает почти ровно нашу идею (news+RSS 24/7 → фильтр → SEO-рерайт → дашборд → автопубликация). Но: это соло-инди из UK с крошечным следом отзывов (риск исполнения и долгожительства), **фильтр — примитивный keyword-matching, а не скоринг релевантности**, нет AEO и нет привязки к каталогу товаров. Это и есть размер нашего клина: всё, что у них тонко — мы делаем толсто.

**GrackerAI** доказывает, что модель «реалтайм-новости → авто-AEO-контент» коммерчески работает — но только в кибербезе. Все остальные вертикали открыты.

### 1.4 White space — наши 5 точек дифференциации

Ни у одного конкурента нет больше **двух** из этих пяти:

1. **Настоящий обучаемый скоринг релевантности под аудиторию бренда** (а не keyword include/exclude). Это самый защищаемый клин. Feedly Leo умеет — но не пишет.
2. **Привязка инфоповода к конкретным товарам клиента** (не просто «brand voice», а «вот эта новость → вот эти товары/подборка»). Для LOOTON это прямо коммерческий потенциал из её «Критериев».
3. **AEO-native структура черновика** (answer-first, FAQ-schema, entities, JSON-LD) — поверх свежей новости. У ньюсджекеров этого нет, у AEO-тулов нет новостей.
4. **Кураторская ежедневная очередь черновиков** как ядро UX (не bulk-спиннер, а «вот сегодняшние релевантные истории, уже в черновиках, approve/edit/kill»).
5. **Мультибренд / агентский ресейл** — продукт перепродаётся агентствам, ведущим много клиентских блогов.

### 1.5 Бенчмарки цен (якоря для нашей сетки)

- **Self-serve автопилот-райтеры (наш основной comp set):** вход $9–49; «золотая середина» автопилота — **~$99/мес за один бренд**; агентский мульти-бренд $179–399; done-for-you $799–2000+.
- **AEO generate (премиум):** $295–545 (Goodie, AthenaHQ); enterprise $2–5k.
- **Листенинг:** Feedly ~$8–13, Brand24/BuzzSumo $199–999, Meltwater $15–100k+/год.

**Вывод по цене:** гравитация категории — **~$99/мес за один бренд на автопилоте**. Можем стоять чуть выше keyword-пака за счёт релевантности + AEO, но ниже $295+ AEO-генераторов. Маржа и липкость живут в агентском мульти-бренд тарифе. Детали — в `06_pricing_unit_economics.md`.

---

## 2. Ingestion (сбор источников)

### 2.1 RSS жив, но с гнильцой

По свежему обзору Web Feeds 2026 (196k сайтов): **~36% значимых сайтов** отдают autodiscovery фида, парсинг успешен в 98.3%, **но только ~38% фидов реально свежие** (многие CMS отдают протухшие). Вывод: **жди фид примерно у 1 из 3 целей, но всегда проверяй свежесть**.

Подтверждённо рабочие fashion-фиды:

| Сайт | Фид |
|---|---|
| Hypebeast | `https://hypebeast.com/feed` (+ категорийные `/footwear/feed`) |
| Business of Fashion | `https://www.businessoffashion.com/feed` (пейволл → только excerpts) |
| WWD | `https://wwd.com/feed/` и директория `https://wwd.com/rss-feeds/` |
| Vogue Business | нативный фид не подтверждён — перепроверить, иначе RSS-Bridge |

Для сайтов без фидов — синтезируем фид через **RSS-Bridge** (PHP, поддерживается, free) или **RSSHub**. Для усечённых/пейволльных — **FiveFilters Full-Text RSS** (~$10/мес).

### 2.2 Скрапинг — каскад от дешёвого к дорогому

| Тул | Что | Markdown-выход | JS | Анти-бот | Цена |
|---|---|---|---|---|---|
| **Crawl4AI** (OSS) | Self-hosted LLM-friendly краулер | ✅ (fit markdown) | ✅ | stealth, BYO proxies | **Free**; инфра ~$20–40/мес |
| **Firecrawl** | Hosted scrape/crawl/extract API | ✅ (лучший) | ✅ | proxies + stealth | Free 1k; Hobby $16; Std $83 |
| **ScrapingBee** | Single-endpoint API | ✅ | ✅ | classic/stealth | $49 (250k cr) |
| **Apify** | Платформа + 45k акторов | ✅ | ✅ | residential proxy | $5 free; Starter $29 |
| **Bright Data** | Прокси-империя + unlocker | JSON | ✅ | **сильнейший** | Web Unlocker $1.50/1k |
| **Zyte** | Smart scraping infra | HTML/structured | ✅ | auto DC↔residential | PAYG $0.13–16/1k |

**Вердикт:** дефолт — **self-hosted Crawl4AI** (бесплатно, чистый markdown, держит JS). **Firecrawl PAYG** — escape hatch для JS-тяжёлых/анти-бот сайтов. **Bright Data/Zyte** — только когда упрёмся в серьёзные анти-бот стены (маркетплейсы).

### 2.3 Экстракция и дедуп

- **Экстракция текста → trafilatura.** Лучшая точность на 3 независимых бенчмарках (F1 0.958), активно поддерживается, отдаёт markdown/JSON/XML и **встроенный SimHash-дедуп** — две задачи одной зависимостью. (Альтернативы: newspaper4k для журналистских метаданных; Mozilla Readability для JS. **Не брать** мёртвые newspaper3k и mercury.)
- **Новизна («новое со вчера»):** **news-sitemap — секретное оружие** (спека Google требует хранить только последние 2 дня → поллинг = лента свежего). RSS: GUID как ключ идентичности. Слать `If-None-Match`/`If-Modified-Since` → 304 = скип. Reference-тулы: changedetection.io, urlwatch.
- **Дедуп (3 уровня):** URL-канонизация (срезать utm/fbclid/сессии, honor `rel=canonical`) → SHA-256 нормализованного текста → near-dup (SimHash Hamming ≤3/64 или MinHash+LSH через datasketch; embeddings cosine ≥0.9 только если рерайты просачиваются).

### 2.4 Архитектура адаптеров

Свой тонкий единый интерфейс, чужая «скучная механика»:

```
SourceAdapter:
  config_schema                 # декларативный конфиг источника
  fetch(state) -> iter[Raw]     # инкрементально через курсор (last_published_at / ETag / since_id)
  normalize(raw) -> Document    # маппинг в ОДНУ каноническую схему
  -> returns new state          # то, что все недостраивают
```

Все адаптеры (RSS, Crawl4AI-скрапер, Telegram, Reddit) отдают единый **canonical Document** (поля — в `03_architecture.md`).

- **Backbone → dlt (dlthub)** — Python-библиотека, не сервер: инкрементальная загрузка, эволюция схемы, ретраи, state. Деплоить нечего.
- **Краулинг-адаптеры → Scrapy** там, где нужна вежливость/ретраи. Простой RSS — `feedparser`.
- **Скип для MVP:** Airbyte, Meltano/Singer, NiFi.

### 2.5 Соцсети (фаза 2) — честная осуществимость

| Платформа | Путь | Стоимость | Вердикт |
|---|---|---|---|
| **Telegram** | MTProto (Telethon/Pyrogram, юзер-аккаунт) | Free | **✅ дружелюбнейший** — читает публичные каналы |
| **Reddit** | Официальный API + PRAW | Free 100 QPM после аппрува (с ноя-2025 пре-аппрув-гейт) | **✅** — заявку подать заранее |
| **X/Twitter** | Pay-per-use / Enterprise | реальный доступ $42k+/мес | **❌ враждебный/дорогой** |
| **Instagram** | Graph API (только бизнес opt-in) | app-review гейт | **❌** не читает произвольный публичный контент |
| **TikTok** | Research API (только академия) | коммерция запрещена | **❌** |

**План:** строим Telegram + Reddit первыми. X/IG/TikTok — только через OAuth собственных аккаунтов клиента, без широкого ингеста.

### 2.6 Стоимость ingestion для MVP

RSS бесплатно, self-hosted Crawl4AI бесплатно, платим (Firecrawl/Bright Data кредиты) только за конкретные сопротивляющиеся сайты. **Итого MVP: ~$30–80/мес.**

---

## 3. AI-пайплайн и cost-metering

### 3.1 Главное

Наш пайплайн `extract → score → generate → feedback` — это детерминированный DAG, **не открытый агент**. Отсюда: **жирный фреймворк (LangChain/LangGraph) не нужен** — plain SDK + Pydantic AI + Instructor. LangGraph оправдан только если стадия генерации станет многошаговым ресёрч-агентом с циклами.

### 3.2 Cost-metering (биллинг-бэкбон)

Требование: мерить $ на каждый AI-запрос, атрибутировать на тенанта, отдавать через API.

| Тул | OSS/Hosted | Атрибуция на тенанта | Billing-grade API | Вердикт |
|---|---|---|---|---|
| **Langfuse** | OSS (MIT), self-host free | ✅ (userId + metadata tenant_id) | ✅ Metrics/Daily Metrics API под биллинг | **Основной для метеринга** |
| **LiteLLM** | OSS (MIT) proxy | ✅ (virtual keys + бюджеты на ключ/тим) | Частично (плоский бюджет) | **Гейтвей + enforcement** |
| **Helicone** | OSS, Cloud | ✅ (custom properties) | ✅ GraphQL | ⚠️ куплен Mintlify нач-2026, роадмап неясен |
| **Portkey** | Gateway OSS, Cloud | ✅ (на уровне роутинга) | ✅ | Альтернатива «всё в одном» |

**Рекомендуемая связка:** `App → LiteLLM proxy (virtual key на тенанта, hard-бюджет) → callback в Langfuse (tag: tenant_id, user_id, stage) → ночью Daily Metrics API → группировка по tenant_id → биллинг`. LiteLLM и Langfuse не пересекаются, у LiteLLM есть нативный Langfuse-callback.

### 3.3 Роутинг моделей — главный рычаг юнит-экономики

Двухуровневый роутинг: **фильтрация — дешёвой моделью** (Gemini Flash-Lite / GPT-nano), **драфтинг — сильной** (Claude Sonnet / GPT-flagship). Это срезает 60–80% наивного счёта. Гейтвей — **self-hosted LiteLLM** (без +5% маркапа OpenRouter). Прототип можно гонять на OpenRouter.

### 3.4 Структурированный вывод

**Instructor + Pydantic** — мапит модель на нативный structured-output провайдера, валидирует, авторетраит. Промпт-онли JSON даёт двузначный % ошибок парсинга в проде. Правила: строгая Pydantic-схема, `description` на каждое поле, enum/bounded int для скоров, поле `reasoning` ПЕРЕД скором (дешёвый chain-of-thought).

### 3.5 Цена за операцию (актуальные модели, апрель 2026)

| Операция | Модель | Стоимость |
|---|---|---|
| Скоринг 1 статьи (~2k in / 250 out) | Gemini Flash-Lite / GPT-nano | **~$0.0002–0.0003** |
| Генерация 1 черновика (~3k in / 2k out) | GPT-mini | ~$0.005 |
| Генерация 1 черновика | Claude Sonnet 4.6 | ~$0.039 |

**Скоринг практически бесплатен, драфтинг — реальный COGS.** Клиент со скорингом 10k статей + 200 черновиков/мес на Sonnet ≈ **$10/мес AI-затрат**; на GPT-mini ≈ $3.5/мес. Закладываем +30–50% буфер на ретраи/few-shot. Детали — в `06_pricing_unit_economics.md`.

### 3.6 SEO/AEO механика

Каждый черновик должен нести: один `<h1>`, логичную иерархию H2/H3, **answer-first** (прямой ответ 40–60 слов в начале секции), FAQ-секцию, явные entities, короткие абзацы/списки/таблицы, и **JSON-LD** (`Article`/`NewsArticle` + `FAQPage` + `BreadcrumbList`). FAQPage-схема — высший AEO-рычаг (страницы с ней попадают в AI Overviews ~3.2× чаще). **Стадия генерации отдаёт тело + JSON-LD одним структурированным ответом** — чтобы схема всегда совпадала с контентом.

---

## 4. SaaS-стек и инфраструктура

Подробное обоснование — в `03_architecture.md`. Сводка решений:

| Слой | Выбор | Почему |
|---|---|---|
| Фронт | **Next.js (App Router) + Flowbite React** | Flowbite Pro куплен; чистая React-интеграция, server actions, деплой на Vercel |
| AI/пайплайн | **FastAPI** (отдельный сервис) | Скрапинг + LLM живут в Python |
| Auth + DB | **Supabase (Postgres + Auth + RLS)** | Дёшево на масштабе ($0.00325/MAU после 50k free), RLS = изоляция тенантов на уровне БД |
| Бойлерплейт | **Makerkit (Next.js/Supabase)** опц. | auth+teams+super-admin из коробки; компоненты заменяем на Flowbite |
| Фоновые задачи | **Trigger.dev** (длинные джобы) или **Celery** (если оркестратор — FastAPI) | managed cron + per-step ретраи; для AI-пайплайна Celery в Python естественнее |
| Биллинг (после MVP) | **Stripe Billing** (metered + tiered) | 0.7% объёма, делает всё нужное; Lago/Orb — когда usage-биллинг станет ядром |
| Хостинг | Vercel (фронт) + Supabase (БД) + Railway/Fly (FastAPI/worker) | ~$40–85/мес на MVP |
| Админка | **Кастом на Flowbite Pro** | Завязана на свою модель данных + AI-spend; Retool — только как времянка |

**Флаги:** (1) Metronome куплен Stripe (закрытие 14.01.2026) — долгосрочный «scale-up» путь usage-биллинга = глубже в Stripe. (2) Все бойлерплейты на Tailwind, но не на Flowbite — закладываем время на замену компонентного слоя на Flowbite Pro.

---

## Источники (ключевые)

- Web Feeds 2026 survey — mnot.net/blog/2026/feed-survey
- trafilatura — github.com/adbar/trafilatura · Zyte article-extraction-benchmark
- Crawl4AI · Firecrawl · Bright Data · Zyte — карточки вендоров
- LLM-цены — tldl.io/resources/llm-api-pricing-2026
- Langfuse cost tracking + Daily Metrics API — langfuse.com/docs
- LiteLLM vs Helicone vs Langfuse — llmcfo.com/research/litellm-vs-helicone-vs-langfuse
- Instructor — python.useinstructor.com
- AEO schema — airops.com/blog/schema-markup-aeo · frase.com FAQ-schema GEO/AEO
- Stripe usage-based billing — stripe.com/billing/usage-based-billing
- Supabase / Makerkit / SaaS Pegasus / Trigger.dev — карточки вендоров
- Конкуренты: AIBlogMax, Arvow, GrackerAI, RankYak, Byword, Feedly Leo, Frase — сайты вендоров
