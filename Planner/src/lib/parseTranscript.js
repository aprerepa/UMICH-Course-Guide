/** POST a transcript PDF to the local pdfplumber API. */

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

/**
 * @param {File} file
 * @returns {Promise<{ courses: ParsedCourse[], counts: Record<string, number> }>}
 */
export async function parseTranscriptPdf(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch("/api/transcript/parse", {
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
