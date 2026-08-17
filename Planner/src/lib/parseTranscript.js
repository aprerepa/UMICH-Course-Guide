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

function parseEndpoint() {
  const base = import.meta.env.VITE_TRANSCRIPT_API_URL?.trim().replace(/\/$/, "");
  if (base) return `${base}/parse`;
  // Local dev: Vite proxies /api/transcript → localhost:8787
  return "/api/transcript/parse";
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
    const msg = json.detail || json.message || `Parse failed (${res.status})`;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return json;
}
