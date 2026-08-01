#!/usr/bin/env node
/**
 * OKF Bundle Structural + Conformance Scan
 *
 * Usage: node okf-scan.js [bundle-path]
 *   bundle-path defaults to "docs/" relative to cwd
 *
 * Outputs JSON to stdout:
 *   { bundlePath, totalFiles, totalLinksChecked,
 *     brokenLinks[], orphanedPages[], stubPages[], indexGaps[],
 *     missingFrontmatter[], missingType[] }
 *
 * Exit codes: 0 = scan complete (issues may still exist), 1 = fatal error
 *
 * OKF v0.2 conformance (SPEC §11): every non-reserved .md must carry a parseable
 * YAML frontmatter block with a non-empty `type`. Reserved files (index.md, log.md)
 * are navigation/history, not concepts, and are exempt from the type requirement.
 *
 * Skips:
 *   - External links (http/https/mailto)
 *   - Cross-project OKF links (paths traversing outside the bundle root)
 */

"use strict"

const fs = require("fs")
const path = require("path")

// ── Config ──────────────────────────────────────────────────────────────────
const STUB_THRESHOLD = 5 // lines of real content below which a page is a stub
const OKF_MARKER = "okf" // cross-project link marker — skip these
const RESERVED = new Set(["index.md", "log.md"]) // OKF reserved filenames

const bundlePath = path.resolve(process.argv[2] || "docs")

if (!fs.existsSync(bundlePath)) {
  process.stderr.write("Error: bundle path not found: " + bundlePath + "\n")
  process.exit(1)
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function walkDir(dir) {
  const entries = []
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) entries.push(...walkDir(full))
    else if (entry.isFile() && entry.name.endsWith(".md")) entries.push(full)
  }
  return entries
}

function relBundle(absPath) {
  return "/" + path.relative(bundlePath, absPath).replace(/\\/g, "/")
}

function isReserved(absPath) {
  return RESERVED.has(path.basename(absPath))
}

/**
 * Extract internal links from markdown content.
 * Returns hrefs (anchor-stripped) that are not external and not OKF cross-project.
 */
function extractLinks(content) {
  const re = /\[[^\]]*\]\(([^)]+)\)/g
  const links = []
  let m
  while ((m = re.exec(content)) !== null) {
    const raw = m[1].split("#")[0].trim()
    if (!raw) continue
    if (raw.startsWith("http") || raw.startsWith("mailto:")) continue
    if (raw.includes(OKF_MARKER)) continue
    links.push(raw)
  }
  return links
}

/**
 * Resolve a markdown link href to an absolute filesystem path.
 * OKF-absolute links (/architecture.md) resolve relative to bundlePath.
 * Relative links resolve relative to the source file's directory.
 */
function resolveHref(href, sourceFile) {
  if (href.startsWith("/")) return path.join(bundlePath, href)
  return path.resolve(path.dirname(sourceFile), href)
}

/** Strip YAML frontmatter block (--- ... ---) from content. */
function stripFrontmatter(content) {
  const lines = content.split("\n")
  if (lines[0].trim() !== "---") return content
  const closeIdx = lines.findIndex((l, i) => i > 0 && l.trim() === "---")
  if (closeIdx === -1) return content
  return lines.slice(closeIdx + 1).join("\n")
}

/**
 * Lightweight frontmatter parse (no YAML dependency).
 * Returns { hasFrontmatter, type }. `type` is null when absent/empty.
 */
function parseFrontmatter(content) {
  const lines = content.split("\n")
  if (lines[0].trim() !== "---") return { hasFrontmatter: false, type: null }
  const closeIdx = lines.findIndex((l, i) => i > 0 && l.trim() === "---")
  if (closeIdx === -1) return { hasFrontmatter: false, type: null }
  let type = null
  for (const line of lines.slice(1, closeIdx)) {
    const m = line.match(/^type\s*:\s*(.*)$/)
    if (m) {
      type = m[1].trim().replace(/^["']|["']$/g, "")
      break
    }
  }
  return { hasFrontmatter: true, type: type && type.length ? type : null }
}

/** Count lines of real content (non-blank, non-heading) after stripping frontmatter. */
function countContentLines(content) {
  const body = stripFrontmatter(content)
  return body.split("\n").filter((line) => {
    const t = line.trim()
    return t.length > 0 && !t.startsWith("#")
  }).length
}

// ── Scan ─────────────────────────────────────────────────────────────────────
const allFiles = walkDir(bundlePath)
const fileSet = new Set(allFiles)
const linkedTo = new Map() // absolutePath → Set<sourcePaths>

const brokenLinks = []
const stubPages = []
const missingFrontmatter = []
const missingType = []
let totalLinksChecked = 0

for (const file of allFiles) {
  const content = fs.readFileSync(file, "utf8")
  const links = extractLinks(content)
  totalLinksChecked += links.length

  for (const href of links) {
    const resolved = resolveHref(href, file)
    const candidates = [resolved, resolved + ".md"] // tolerate missing extension
    const target = candidates.find((c) => fileSet.has(c))

    if (target) {
      if (!linkedTo.has(target)) linkedTo.set(target, new Set())
      linkedTo.get(target).add(file)
    } else {
      // Verify the path wouldn't escape the bundle root before reporting as broken
      const rel = path.relative(bundlePath, resolved)
      if (!rel.startsWith("..")) {
        brokenLinks.push({
          source: relBundle(file),
          href,
          resolved: relBundle(resolved),
        })
      }
    }
  }

  // OKF frontmatter conformance (reserved files are exempt from the type rule)
  if (!isReserved(file)) {
    const fm = parseFrontmatter(content)
    if (!fm.hasFrontmatter) missingFrontmatter.push(relBundle(file))
    else if (!fm.type) missingType.push(relBundle(file))

    // Stub check (concepts only)
    const lines = countContentLines(content)
    if (lines < STUB_THRESHOLD) {
      stubPages.push({ path: relBundle(file), contentLines: lines })
    }
  }
}

// ── Orphans (reserved navigation/history files are never orphans) ─────────────
const orphanedPages = allFiles
  .filter((f) => !isReserved(f) && !linkedTo.has(f))
  .map(relBundle)

// ── Index coverage gaps ───────────────────────────────────────────────────────
const indexGaps = []
const indexFiles = allFiles.filter((f) => path.basename(f) === "index.md")

for (const indexFile of indexFiles) {
  const dir = path.dirname(indexFile)
  const content = fs.readFileSync(indexFile, "utf8")
  const links = extractLinks(content)
  const resolved = new Set(links.map((href) => resolveHref(href, indexFile)))

  const siblings = allFiles.filter(
    (f) => path.dirname(f) === dir && f !== indexFile && !isReserved(f),
  )
  for (const sibling of siblings) {
    const withoutExt = sibling.replace(/\.md$/, "")
    if (!resolved.has(sibling) && !resolved.has(withoutExt)) {
      indexGaps.push({ index: relBundle(indexFile), missing: relBundle(sibling) })
    }
  }
}

// ── Output ────────────────────────────────────────────────────────────────────
const result = {
  bundlePath,
  totalFiles: allFiles.length,
  totalLinksChecked,
  brokenLinks,
  orphanedPages,
  stubPages,
  indexGaps,
  missingFrontmatter,
  missingType,
}

process.stdout.write(JSON.stringify(result, null, 2) + "\n")
