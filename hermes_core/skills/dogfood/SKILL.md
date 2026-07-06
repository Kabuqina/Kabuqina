---
name: dogfood
description: Exploratory QA of web apps: find bugs, evidence, reports.
version: 1.0.0
metadata:
  hermes:
    tags: [qa, testing, browser, web, dogfood]
    category: dogfood
---

# Dogfood: Systematic Web Application QA Testing

## Overview

Use this skill to run systematic exploratory QA testing of web applications
with the browser toolset. Navigate the app, interact with elements, capture
evidence, classify issues, and produce a structured report.

## Prerequisites

- Browser toolset must be available: `browser_navigate`, `browser_snapshot`,
  `browser_click`, `browser_type`, `browser_vision`, `browser_console`,
  `browser_scroll`, `browser_back`, and `browser_press`.
- The user provides a target URL and testing scope.

## Inputs

Ask for or infer:

1. Target URL.
2. Scope: focused area or full site.
3. Output directory, defaulting to `./dogfood-output`.

## Workflow

### Phase 1: Plan

Create an output directory with `screenshots/` and `report.md`. Identify the
scope, then build a rough sitemap covering navigation, key flows, forms,
interactive elements, and edge cases.

### Phase 2: Explore

For each page or feature:

1. Navigate with `browser_navigate`.
2. Inspect structure with `browser_snapshot`.
3. Check JavaScript errors with `browser_console(clear=true)`.
4. Use `browser_vision(..., annotate=true)` to inspect visual layout and refs.
5. Interact with elements using `browser_click`, `browser_type`,
   `browser_press`, `browser_scroll`, and `browser_back`.
6. After each significant interaction, re-check `browser_console` and inspect
   visual or DOM changes.

### Phase 3: Collect Evidence

For every issue, capture:

- URL.
- Steps to reproduce.
- Expected behavior.
- Actual behavior.
- Console errors, if any.
- Screenshot path from `browser_vision`.

Classify each issue with `references/issue-taxonomy.md`.

### Phase 4: Categorize

De-duplicate related findings, assign final severity and category, sort by
severity, and count findings by severity and category.

### Phase 5: Report

Generate the final report from `templates/dogfood-report-template.md` and save
it to `{output_dir}/report.md`. Include `MEDIA:<screenshot_path>` references
for evidence screenshots.

## Tools Reference

| Tool | Purpose |
|------|---------|
| `browser_navigate` | Go to a URL |
| `browser_snapshot` | Get DOM text snapshot |
| `browser_click` | Click an element by ref or text |
| `browser_type` | Type into an input field |
| `browser_scroll` | Scroll the page |
| `browser_back` | Go back in browser history |
| `browser_press` | Press a keyboard key |
| `browser_vision` | Screenshot and AI visual analysis; use `annotate=true` |
| `browser_console` | Get JS console output and errors |

## Tips

- Always check `browser_console()` after navigating and after significant
  interactions.
- Use `annotate=true` when element refs are unclear.
- Test both valid and invalid inputs.
- Scroll through long pages and inspect below-the-fold content.
- Test keyboard navigation and multi-step flows.
- Include screenshots and console output in the final report when relevant.
