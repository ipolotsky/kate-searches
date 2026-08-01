# OKF Bundle Audit — KateSearches docs

**Date:** [DATE]
**Scope:** [N] files · [N] links checked · 8 scenarios

---

## Structural + OKF conformance scan

| Check                              | Result              | Status          |
| ---------------------------------- | ------------------- | --------------- |
| Broken links                       | [N] / [total links] | ✓ PASS / ✗ FAIL |
| Orphaned pages                     | [N] / [total files] | ✓ PASS / ✗ FAIL |
| Missing frontmatter (OKF)          | [N]                 | ✓ PASS / ✗ FAIL |
| Missing/empty `type` (OKF)         | [N]                 | ✓ PASS / ✗ FAIL |
| Stub pages (< 5 content lines)     | [N]                 | ✓ PASS / ✗ FLAG |
| Index coverage gaps                | [N]                 | ✓ PASS / ✗ FLAG |

_OKF v0.2 conformance: every non-reserved `.md` needs parseable frontmatter with a non-empty
`type`. Reserved files (`index.md`, `log.md`) are exempt._

---

## Semantic navigation test

[N] FOUND · [N] PARTIAL · [N] NOT FOUND · avg [N] hops

| #   | Question                                            | Grade                   | Hops | Finding        |
| --- | --------------------------------------------------- | ----------------------- | ---- | -------------- |
| Q1  | Pipeline stages a news item passes through, in order | FOUND/PARTIAL/NOT FOUND | [N]  | [one sentence] |
| Q2  | What decides if a news item passes selection        |                         |      |                |
| Q3  | How tenant isolation is enforced at the DB layer    |                         |      |                |
| Q4  | LLM gateway + metering, and model-routing rule      |                         |      |                |
| Q5  | Which sources are ingested in the MVP               |                         |      |                |
| Q6  | COGS basis and pricing-tier structure               |                         |      |                |
| Q7  | How a draft is composed (инфоповод × бренд); SKU layer? |                     |      |                |
| Q8  | Deploy / CI-CD structure (env, rollout, test-gates) |                         |      |                |

---

## Issues to fix

1. **[File path]** — [what is wrong] → [specific one-line action]
2. …

_Group structural/OKF issues first, then semantic ones._

---

_Audit method: automated structural + OKF conformance scan (`scripts/okf-scan.js`) +
8-question semantic navigation test navigated from `docs/index.md`._
