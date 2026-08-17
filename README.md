# UMich Course Guide

Unofficial University of Michigan undergraduate Course Guide: browse majors by published requirement groups, inspect Schedule of Classes (SOC) sections, and optionally sign in for a personalized view of remaining courses.

**Live app:** [https://umich-course-guide.vercel.app](https://umich-course-guide.vercel.app)

## Features

### Guest course guide

- Continue without an account and browse the full published catalog
- Filter by **major**, **requirement group**, **course level**, and **semester**
- Search by course code or title
- Expand a course for sections, meeting times, instructors, and historic offering patterns
- Course lists aligned with published major requirements (cores, electives, capstones, and similar groups)

### Personalized guide (signed-in)

- Email/password **sign up** and **sign in** (Supabase Auth)
- Declare one or more **majors / sub-majors** at signup; change them later in Settings
- Signed-in home is scoped to your declared programs (guest mode still shows all majors)
- Add **completed courses** by code, or upload an unofficial transcript PDF
- Taken courses are hidden from the remaining-course list
- Requirement groups that are complete are still listed, marked as completed
- Completion is computed from major configs + `groupRules` (not from the current-term SOC snapshot)
- Account menu: Settings, sign out, or return to the login screen
- Settings: update majors, or **delete your account** (type `delete my account` to confirm)

Transcript PDF parsing runs through a small local API (`npm run transcript-api`). It is not part of the Vercel static deploy.

## Tech stack

- [React](https://react.dev/) + [Vite](https://vite.dev/)
- [Supabase](https://supabase.com/) for accounts, declared programs, and completed courses
- Course data sourced from the [UMich Schedule of Classes API](https://developer.umich.edu/)
- Major requirement lists in `Planner/config/majors`; completion rules in `Planner/config/rules`

## Getting started

```bash
cd Planner
cp .env.example .env   # then fill in Supabase keys for sign-in
npm install
npm run dev
```

Open the URL Vite prints (usually `http://localhost:5173`).

Without `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, the app stays in guest mode.

### Transcript uploads (local)

In a second terminal:

```bash
cd Planner
npm run transcript-api
```

Keep `npm run dev` running; Vite proxies `/api/transcript` to that server.

### Production build

```bash
cd Planner
npm run build
npm run preview
```

## Deploy

Production: [https://umich-course-guide.vercel.app](https://umich-course-guide.vercel.app)

The frontend is a static Vite app. On [Vercel](https://vercel.com):

1. Import this repository
2. Set the **Root Directory** to `Planner`
3. Add environment variables (Production + Preview):
   - `VITE_SUPABASE_URL`
   - `VITE_SUPABASE_ANON_KEY`
4. Deploy (`npm run build`, output `dist`)

Vite inlines `VITE_*` at **build** time, so change those vars and redeploy for sign-in to appear on the live site.

Run the SQL in the repo root once in the Supabase SQL editor: `course_guide_schema_mvp.sql`, `course_guide_grants.sql`, `course_guide_delete_account.sql`.

## Project structure

```
Planner/                 # Frontend application
Planner/config/majors/   # Per-major course / requirement lists
Planner/config/rules/    # Per-major completion rules
Planner/transcript_api/  # Local PDF transcript parser
UMICH Majors/            # Tools for collecting major requirement data
```

## Disclaimer

This is an unofficial student project and is not affiliated with or endorsed by the University of Michigan. Always confirm requirements with your advisor and the official Course Guide / Atlas.
