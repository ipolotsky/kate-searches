---
name: okf-audit
user-invocable: true
description: >
  Audit the KateSearches docs/ OKF knowledge bundle for conformance, navigation
  and search quality. Use when asked to test the docs, check the knowledge base,
  validate the OKF bundle, or verify that developers can find answers. Runs an
  automated structural + OKF-conformance scan then an 8-question semantic
  navigation test, and produces a compact report.
compatibility: Requires Node.js (any version ≥ 18) for the structural scan script.
metadata:
  author: DFG
  version: "1.0.0"
---

# OKF Docs Audit

Two-part audit of the OKF v0.2 bundle at `docs/`: an automated structural +
conformance scan, then a semantic navigation test. Run immediately without asking
for confirmation.

Background on the format:
[OKF SPEC v0.2](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).
The bundle root is `docs/`; `docs/index.md` is the directory listing and `docs/log.md`
the change history — both are reserved (not concepts).

## Step 1 — Structural + OKF scan

```bash
node .claude/skills/okf-audit/scripts/okf-scan.js docs/
```

The script outputs JSON. Extract:

| Field                              | Meaning                                             | Pass condition    |
| ---------------------------------- | --------------------------------------------------- | ----------------- |
| `brokenLinks`                      | Links with no matching file                         | must be empty     |
| `orphanedPages`                    | Concept files not linked from anywhere              | must be empty     |
| `missingFrontmatter`               | Non-reserved `.md` with no parseable YAML frontmatter | must be empty     |
| `missingType`                      | Frontmatter present but no non-empty `type`         | must be empty     |
| `stubPages`                        | Concept files with < 5 real content lines           | flag any found    |
| `indexGaps`                        | Siblings not listed in their section `index.md`     | flag any found    |
| `totalFiles` / `totalLinksChecked` | Scope of the scan                                   | include in report |

`missingFrontmatter` / `missingType` are the core OKF v0.2 conformance checks (SPEC §11):
every non-reserved `.md` must carry parseable frontmatter with a non-empty `type`.

If the script exits with an error, confirm that `docs/` exists at the repo root and that
Node.js is available.

## Step 2 — Semantic navigation test

For each question below, navigate from `docs/index.md` as a developer would — read the
index, follow links, open files. Grade every question:

- **FOUND** — clear, complete answer reachable in ≤ 3 hops
- **PARTIAL** — answer exists but is incomplete or requires > 3 hops / multiple disconnected files
- **NOT FOUND** — no answer in the bundle

Test questions (run all 8):

1. What are the pipeline stages a news item passes through, in order?
2. What decides whether a news item passes selection (scoring model / criteria)?
3. How is tenant isolation enforced at the DB layer?
4. Which LLM gateway and metering tools are used, and how is model routing chosen?
5. Which sources are ingested in the MVP?
6. What is the COGS basis and how are pricing tiers structured?
7. How is a post draft composed (инфоповод × бренд) — is there a product/SKU layer?
8. How is deploy / CI-CD structured (environments, rollout, test-gates)?

Record: question number, grade, hops-to-answer (integer or "4+"), one-sentence finding.

## Step 3 — Report

Format the output using the template in `references/report-template.md`.

List any issues (broken links, missing frontmatter/type, stubs, index gaps,
PARTIAL/NOT FOUND questions) as a numbered action list: file path + one-line fix. Group
structural/OKF issues first, then semantic ones.

## Gotchas

- The bundle uses OKF-absolute links (`/architecture.md`) that resolve under `docs/` on
  disk. The script handles this automatically (bundle root = the scanned path).
- Cross-project links containing `okf` in the path point outside this bundle and are
  intentionally excluded from the scan — do not treat them as broken.
- Reserved files (`index.md`, `log.md`) are exempt from the `type` requirement, stub
  detection, and orphan reporting — they are navigation/history, not concepts.
- Stub detection strips YAML frontmatter before counting content lines. A file with only
  frontmatter and headings counts as 0 content lines.
- OKF consumers tolerate broken links and missing optional fields; the hard failures for
  this bundle are `brokenLinks`, `orphanedPages`, `missingFrontmatter`, and `missingType`.
