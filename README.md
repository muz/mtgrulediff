# MTG Rule Diff

A tool for presenting Magic: The Gathering Comprehensive Rules updates in a clear, human-friendly format — statically hosted on GitHub Pages.

## What it does

Magic: The Gathering maintains a [Comprehensive Rules](https://magic.wizards.com/en/rules) document that is updated with each new set release. Between versions, rules can:

- Be **added** (new rule numbers)
- Be **removed** (rule numbers retired)
- Be **renumbered** (same content, different number)
- Have their **text updated** (errata, clarifications, rewordings)

This project processes two versions of the rules document, diffs them, and generates static HTML pages that highlight exactly what changed — making it easy to understand what Wizards actually modified without reading hundreds of pages.

## How it works

```
rules/          ← raw rules text files, one per release (e.g. 20250411.txt)
scripts/        ← scripts that parse, diff, and generate HTML
html/           ← generated output, served via GitHub Pages
```

1. Add a new rules text file to `rules/` when a new set releases
2. Run the generation script — it diffs the new file against the previous release and writes output to `html/`
3. Commit and push — GitHub Pages serves the updated site automatically

## Current scripts

- `scripts/parse_rules.py` parses one rules file into structured JSON (`rules` + `glossary`).
- `scripts/diff_rules.py` compares two rules files and classifies changes:
	- unchanged
	- modified
	- added
	- removed
	- renumbered (exact text)
	- renumbered and modified (high-similarity text)
- `scripts/build_data.py` discovers all files in `rules/` (sorted by YYYYMMDD in filename), diffs each adjacent pair, and writes static JSON artifacts to `html/data/`.

## Quick start

Parse one file:

```bash
python3 scripts/parse_rules.py "rules/MagicCompRules 20260417.txt" > /tmp/parsed.json
```

Diff two files:

```bash
python3 scripts/diff_rules.py \
	"rules/MagicCompRules 20260227.txt" \
	"rules/MagicCompRules 20260417.txt" \
	-o /tmp/diff.json
```

Build all site data (for static hosting):

```bash
python3 scripts/build_data.py
```

This generates:

- `html/data/releases.json`
- `html/data/diffs/<old_yyyymmdd>_to_<new_yyyymmdd>.json`

Build everything in one command:

```bash
python3 scripts/build_all.py
```

This runs both data generation and HTML generation, then leaves a ready-to-serve site at `html/index.html`.

## Output

Each rules update gets its own page showing:

- **Added rules** — new entries highlighted in green
- **Removed rules** — deleted entries highlighted in red
- **Renumbered rules** — rules that moved to a new number
- **Modified rules** — inline diffs showing exactly which words changed

An index page lists all tracked releases in reverse chronological order so users can browse the history of rules changes over time.

## Hosting

The `html/` directory is served directly via GitHub Pages. No build step is required at serve time — all diffs are pre-generated.

## Data format

Rules are provided as plain-text files — one file per release. Each rule is identified by a rule number (e.g. `100.1`, `702.19c`) followed by its text. Rules are grouped into numbered sections and subsections.

> Data files will be added as the project develops.

## Goals

- **Accuracy** — correctly identify renumbered rules vs. truly new/removed ones
- **Readability** — word-level diffs so small wording changes are immediately visible
- **Browsability** — fast, lightweight static pages with no JavaScript framework required
- **History** — every past update preserved and linkable
