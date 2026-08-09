# UMICH Majors

Personal project (not Akaike). Fetches the undergraduate majors list from UMich
Admissions, then optionally fetches each program page and extracts structured
fields with **your own** OpenAI-compatible LLM API.

**Source listing:** https://admissions.umich.edu/academics-majors/majors-degrees

This folder does **not** use Tokenplex / `TOKENPLEX_*`. Keys live only in
`UMICH Majors/.env` (see `.env.example`).

## Setup

```bash
cd "UMICH Majors"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # only if HTTP fetch is too thin / JS-heavy
cp .env.example .env          # fill UMICH_LLM_* when you want extract
```

Put LLM keys only in **this** folder’s `.env` (see `.env.example`).

## Pipeline

```
1. list   — HTTP (→ Playwright) listing page → parse table → majors.jsonl
2. fetch  — GET each major's program URL → page.html / page.txt
3. enrich — LLM JSON extract from page text (optional; needs UMICH_LLM_*)
```

No Serper step: the listing page already has the canonical URLs.

## Commands

```bash
cd "/Users/adharvprerepa/Course_Guide/UMICH Majors"
source .venv/bin/activate   # or: python3 -m venv .venv && pip install -r requirements.txt

# Step 1 — listing only (no LLM)
python -m umich_majors.cli list
# or: python fetch_majors.py

# Step 2 — program page → hop to Requirements / Degree Requirements → LLM-ready text
# Writes requirements/<major-id>/ (program_page.*, requirements_page.*, meta.json)
python -m umich_majors.cli requirements --id "Statistics"
python -m umich_majors.cli requirements --limit 5

# Step 3 — one program page only, no hop / no LLM
python -m umich_majors.cli fetch --id "Aerospace Engineering"

# Step 4 — fetch + overview LLM extract (needs .env) — optional, not course-code extract
python -m umich_majors.cli enrich --id "Aerospace Engineering"
python -m umich_majors.cli enrich --limit 5
python -m umich_majors.cli enrich --limit 10 --skip-llm
```

## Outputs

| Path | Contents |
|------|----------|
| `output/majors.jsonl` | Listing rows (`id`, `name`, `school_college`, `url`, `is_submajor`) |
| `output/majors.csv` / `majors.json` | Same listing |
| `requirements/<id>/` | Per major: program page + hopped requirements page (`requirements_page.llm.txt` for LLM) |
| `output/enrichment.jsonl` | Appended enrich rows (overview extract) |
| `runs/<id>/` | Per-major enrich artifacts |
