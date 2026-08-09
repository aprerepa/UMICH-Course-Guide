# UMich Course Guide

Browse undergraduate courses by major using UMich Schedule of Classes (SOC) data and program requirement lists.

| Folder | Purpose |
|--------|---------|
| [`Planner/`](Planner/) | Vite + React course guide (what you deploy) |
| [`UMICH Majors/`](UMICH%20Majors/) | Pipeline: scrape major pages → LLM extract → major configs |

## Quick start (frontend)

```bash
cd Planner
cp .env.example .env   # only needed for SOC fetch scripts, not for the UI
npm ci
npm run dev
```

Open the local Vite URL. Course data lives in `Planner/src/data/courses.json`.

## Deploy (Vercel)

1. Push this repo to GitHub.
2. Import the project at [vercel.com](https://vercel.com).
3. Set **Root Directory** to `Planner`.
4. Framework: Vite (auto). Build: `npm run build` → output `dist`.
5. Deploy.

No env vars are required for the static guide. (Later: Supabase keys for personalization.)

Redeploy after updating course data:

```bash
cd Planner
python3 scripts/fetch_courses.py --resync   # or --missing
npm run build   # or just git push and let Vercel build
```

## SOC course fetch (local)

Credentials stay in `Planner/.env` (gitignored):

```bash
cd Planner
cp .env.example .env
# set UMICH_SOC_CLIENT_ID and UMICH_SOC_CLIENT_SECRET from developer.umich.edu
# subscribe the app to the Schedule of Classes API product

python3 scripts/fetch_courses.py --missing
python3 scripts/fetch_courses.py --resync
```

## Majors extract pipeline (local)

```bash
cd "UMICH Majors"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # UMICH_LLM_* for Gemini / OpenAI-compatible extract

python -m umich_majors.cli list
python -m umich_majors.cli requirements --id "Computer Science"
python -m umich_majors.cli extract --id "…" --force
```

Copy or sync extracted majors into `Planner/config/majors/`, then run the SOC fetch above.

## Secrets

Never commit:

- `Planner/.env`
- `UMICH Majors/.env`

Examples only: `*.env.example`.
