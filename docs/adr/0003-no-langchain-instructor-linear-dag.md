---
type: ADR
title: "ADR-0003 — LLM-оркестрация: plain SDK + Instructor, без LangChain"
description: Линейный DAG на plain SDK + Instructor вместо LangChain/LangGraph.
status: accepted
tags: [adr, architecture, ai]
generated:
  by: human:alexander.polyakov
  at: 2026-08-01
---

# ADR-0003 — LLM-оркестрация: plain SDK + Instructor, без LangChain

**Статус:** accepted · **Дата решения:** 2026-06-30.

В контексте LLM-пайплайна `extract → score → generate → feedback`,
сталкиваясь с необходимостью надёжного structured-output при простом линейном потоке с одной развилкой (порог),
мы выбрали **plain provider SDK + Instructor + Pydantic** на линейном DAG,
и отвергли LangChain/LangGraph (overkill для линейного DAG, лишняя абстракция и зависимости),
чтобы получить прозрачный код и надёжный JSON с авторетраями при меньшем числе зависимостей,
принимая как компромисс, что оркестрацию и ретраи пишем сами и не пользуемся готовыми интеграциями фреймворка.

Обоснование — [архитектура §10](/architecture.md); контур вызовов — [AI-пайплайн §1](/ai-pipeline-prompts.md).
