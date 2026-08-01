# Docs Update Log

## 2026-08-01 (audit follow-up)
* **Refactor**: Grouped the three plan docs into a new [`plans/`](plans/index.md) section
  (`m1-ingestion-plan`, `launch-plan`, `handoff`) with a section index; updated the root
  [index](index.md) and all incoming links (`deployment`, `adr/0005`, `handoff`).
* **Navigation**: Sharpened root [index](index.md) descriptions for tenant-isolation (Q3),
  MVP-sources (Q5), scoring rubric (Q2) and generation-symbiosis (Q7) so each is one hop.
* **Refactor**: Extracted the decision log into a new [`adr/`](adr/index.md) section — nine
  Y-Statement ADRs (0001–0009). Replaced the `D1–D4` table in [overview](overview.md) with a
  pointer, keeping the self-serve-vs-billing tension note.
* **Navigation**: Reduced hop count for "pipeline stages in order" (Q1) and "LLM gateway +
  metering + routing" (Q4) — made [AI-пайплайн §1](ai-pipeline-prompts.md) a self-complete
  canonical source and sharpened the [index](index.md) description so both are reachable in one hop.

## 2026-08-01
* **Initialization**: Converted `docs/` to an OKF v0.2 bundle — renamed concept files to
  descriptive slugs, added YAML frontmatter (`type` + title/description/status/tags/generated)
  to every concept, and split the old `00_README.md` into a reserved [index](index.md) listing
  plus an [overview](overview.md) concept (decision log, reading order, glossary).
* **Update**: Rewrote internal cross-references from backtick filenames to OKF-absolute
  markdown links (e.g. `[архитектура](/architecture.md)`).
* **Creation**: Added the `/okf-audit` skill (structural + OKF conformance + semantic
  navigation) to keep the bundle healthy.
