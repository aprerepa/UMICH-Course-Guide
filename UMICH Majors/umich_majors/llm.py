"""OpenAI-compatible chat client for UMICH Majors (not Tokenplex)."""
from __future__ import annotations

import json
import re
import socket
import time
import urllib.error
import urllib.request

from umich_majors.config import llm_config

USAGE = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}


def chat(
    messages: list[dict],
    *,
    max_tokens: int = 2000,
    temperature: float = 0,
    model: str | None = None,
    retries: int = 4,
    timeout: int = 120,
) -> str:
    base, key, default_model = llm_config()
    payload = {
        "model": model or default_model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    body = json.dumps(payload).encode()
    url = base.rstrip("/") + "/chat/completions"
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
            usage = data.get("usage") or {}
            USAGE["prompt"] += usage.get("prompt_tokens", 0)
            USAGE["completion"] += usage.get("completion_tokens", 0)
            USAGE["total"] += usage.get("total_tokens", 0)
            USAGE["calls"] += 1
            return data["choices"][0]["message"].get("content") or ""
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
        ):
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    return ""


def chat_json(system: str, user: str, *, max_tokens: int = 2000, **kw) -> dict | list | None:
    txt = (
        chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            max_tokens=max_tokens,
            **kw,
        )
        or ""
    ).strip()
    # Strip markdown fences if the model wraps JSON
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", txt, re.I)
    if fence:
        txt = fence.group(1).strip()
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", txt)
    if not m:
        return None
    blob = m.group(1)
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        # Truncated JSON: try closing open braces/brackets
        repaired = blob.rstrip().rstrip(",")
        for closer in ("}", "]}", "}}", "]}}"):
            try:
                return json.loads(repaired + closer)
            except json.JSONDecodeError:
                continue
        return None
