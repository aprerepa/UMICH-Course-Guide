"""OpenAI-compatible chat client for UMICH Majors (not Tokenplex)."""
from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request

from umich_majors.config import llm_config

USAGE = {"prompt": 0, "completion": 0, "total": 0, "calls": 0}

# Free-tier RPM/RPD is often per model — rotate on 429 to stretch one API key.
# Override with UMICH_LLM_MODELS=model-a,model-b,...
#
# For course-list JSON extract we want models that return content in
# `message.content` without burning the token budget on hidden "thinking".
# gemini-flash-latest is thinking-capable and often truncates JSON at our
# max_tokens, so it is last-resort only. 2.5-flash* is 404 for new API keys.
_DEFAULT_MODEL_POOL = [
    "gemini-flash-lite-latest",
    "gemini-2.0-flash",
    "gemini-flash-latest",
]

_model_index = 0
_unavailable_models: set[str] = set()


def _model_pool(preferred: str | None = None) -> list[str]:
    env = (os.environ.get("UMICH_LLM_MODELS") or "").strip()
    if env:
        models = [m.strip() for m in env.split(",") if m.strip()]
    else:
        models = list(_DEFAULT_MODEL_POOL)
    if preferred:
        models = [preferred] + [m for m in models if m != preferred]
    # de-dupe, preserve order
    out: list[str] = []
    seen: set[str] = set()
    for m in models:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out or (["gemini-2.5-flash"] if not preferred else [preferred])


def _next_model(pool: list[str], current: str) -> str | None:
    """Pick the next model that is not marked unavailable."""
    global _model_index
    if not pool:
        return None
    start = _model_index
    for _ in range(len(pool)):
        _model_index = (_model_index + 1) % len(pool)
        candidate = pool[_model_index]
        if candidate != current and candidate not in _unavailable_models:
            return candidate
        if _model_index == start and candidate not in _unavailable_models:
            break
    # last resort: any non-unavailable including current
    for m in pool:
        if m not in _unavailable_models:
            return m
    return None


def chat(
    messages: list[dict],
    *,
    max_tokens: int = 2000,
    temperature: float = 0,
    model: str | None = None,
    retries: int = 10,
    timeout: int = 120,
) -> str:
    base, key, default_model = llm_config()
    pool = _model_pool(model or default_model)
    global _model_index
    # Prefer configured / explicit model at the start of each call
    preferred = model or default_model
    if preferred in pool:
        _model_index = pool.index(preferred)
    current_model = pool[_model_index] if pool else preferred

    url = base.rstrip("/") + "/chat/completions"
    last_err: Exception | None = None
    for attempt in range(retries):
        payload = {
            "model": current_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        body = json.dumps(payload).encode()
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
            # Light pacing to stay under RPM across models
            time.sleep(float(os.environ.get("UMICH_LLM_PACING_SEC") or "1.5"))
            return data["choices"][0]["message"].get("content") or ""
        except urllib.error.HTTPError as e:
            last_err = e
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                pass
            if attempt == retries - 1:
                raise

            # Unknown / unsupported model → skip it and rotate
            if e.code in (404, 400):
                lower = err_body.lower()
                if (
                    "no longer available" in lower
                    or "not found" in lower
                    or "is not found" in lower
                    or ("invalid" in lower and "model" in lower)
                ):
                    print(f"  LLM model unavailable ({current_model}) — rotating")
                    _unavailable_models.add(current_model)
                    nxt = _next_model(pool, current_model)
                    if not nxt:
                        raise
                    current_model = nxt
                    time.sleep(1)
                    continue

            if e.code == 429:
                nxt = _next_model(pool, current_model)
                if nxt and nxt != current_model:
                    print(
                        f"  LLM 429 on {current_model} — rotating to {nxt} "
                        f"(attempt {attempt + 1}/{retries})"
                    )
                    current_model = nxt
                    time.sleep(2)
                else:
                    retry_after = e.headers.get("Retry-After") if e.headers else None
                    try:
                        wait = (
                            float(retry_after)
                            if retry_after
                            else min(120.0, 15 * (2 ** min(attempt, 3)))
                        )
                    except ValueError:
                        wait = min(120.0, 15 * (2 ** min(attempt, 3)))
                    print(
                        f"  LLM 429 — all models limited, waiting {wait:.0f}s "
                        f"(attempt {attempt + 1}/{retries})"
                    )
                    time.sleep(wait)
            else:
                time.sleep(min(60.0, 2**attempt))
        except (
            urllib.error.URLError,
            TimeoutError,
            socket.timeout,
            ConnectionError,
            json.JSONDecodeError,
            KeyError,
            IndexError,
        ) as e:
            last_err = e
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    if last_err:
        raise last_err
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
