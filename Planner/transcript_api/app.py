"""Transcript parse API — PDF in, course JSON out."""
from __future__ import annotations

import os

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from parse import parse_transcript_pdf

MAX_BYTES = 10 * 1024 * 1024

DEFAULT_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://umich-course-guide.vercel.app",
]


def _allowed_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "").strip()
    if not raw:
        return DEFAULT_ORIGINS
    return [o.strip() for o in raw.split(",") if o.strip()]


app = FastAPI(title="UMich transcript parser")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins(),
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/")
def health():
    return {"ok": True, "service": "transcript-parser"}


@app.post("/parse")
async def parse(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Upload a PDF transcript")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > MAX_BYTES:
        raise HTTPException(400, "PDF is too large (max 10 MB)")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "File is not a PDF")
    try:
        result = parse_transcript_pdf(data)
    except Exception as e:
        raise HTTPException(422, f"Could not parse transcript: {e}") from e
    if not result["courses"]:
        raise HTTPException(
            422,
            "No courses found. Use an unofficial UMich transcript PDF.",
        )
    return result
