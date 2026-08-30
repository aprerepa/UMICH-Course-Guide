/** POST a transcript PDF to the pdfplumber parse API. */

/**
 * @typedef {{
 *   course_code: string,
 *   title?: string | null,
 *   credits?: number | null,
 *   term_completed?: string | null,
 *   grade?: string | null,
 *   status: "completed" | "in_progress" | "enrolled"
 * }} ParsedCourse
 */

/** Hosted parser (Render). Override with VITE_TRANSCRIPT_API_URL if needed. */
const DEFAULT_TRANSCRIPT_API = "https://umich-transcript-api.onrender.com";

function parseEndpoint() {
  const fromEnv = import.meta.env.VITE_TRANSCRIPT_API_URL?.trim().replace(/\/$/, "");
  if (fromEnv) return `${fromEnv}/parse`;
  // Production: Vercel has no /api/transcript — call Render directly.
  if (import.meta.env.PROD) return `${DEFAULT_TRANSCRIPT_API}/parse`;
  // Local dev: Vite proxies /api/transcript → localhost:8787
  return "/api/transcript/parse";
}

function formatParseError(res, json) {
  if (res.status === 500 || res.status === 502 || res.status === 503) {
    if (import.meta.env.PROD) {
      return "Transcript parser is unavailable. Try again in a minute.";
    }
    return "Start the parser in another terminal: npm run transcript-api (port 8787)";
  }
  const detail = json?.detail ?? json?.message;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
  }
  return `Parse failed (${res.status})`;
}

/**
 * @param {File} file
 * @returns {Promise<{ courses: ParsedCourse[], counts: Record<string, number> }>}
 */
export async function parseTranscriptPdf(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(parseEndpoint(), {
    method: "POST",
    body,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatParseError(res, json));
  }
  return json;
}
