# UMich Course Guide

A web app for exploring University of Michigan undergraduate courses by major. Pick a program, browse its requirement groups (core, electives, capstone, and so on), and inspect section details from the Schedule of Classes.

## Features

- Filter by **major**, **requirement group**, **course level**, and **semester**
- Search by course code or title
- Expand courses to see sections, meeting times, and instructors
- Course lists aligned with published major requirements (e.g. CS LSA/BSE ULCS and Capstone)

## Tech stack

- [React](https://react.dev/) + [Vite](https://vite.dev/)
- Course data sourced from the [UMich Schedule of Classes API](https://developer.umich.edu/)

## Getting started

```bash
cd Planner
npm install
npm run dev
```

Then open the URL Vite prints (usually `http://localhost:5173`).

### Production build

```bash
cd Planner
npm run build
npm run preview
```

## Deploy

The app is a static site. On [Vercel](https://vercel.com):

1. Import this repository
2. Set the **Root Directory** to `Planner`
3. Deploy (build command `npm run build`, output `dist`)

## Project structure

```
Planner/          # Frontend application
UMICH Majors/     # Tools for collecting major requirement data
```

## Disclaimer

This is an unofficial student project and is not affiliated with or endorsed by the University of Michigan. Always confirm requirements with your advisor and the official Course Guide / Atlas.
