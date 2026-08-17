import { useEffect, useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  addCompletedCourse,
  addCompletedCourses,
  completedCodesSet,
  fetchCompletedCourses,
  removeCompletedCourse,
} from "../lib/completedCourses";
import { parseTranscriptPdf } from "../lib/parseTranscript";
import { normalizeCourseCode } from "../lib/completion";

const styles = {
  wrap: {
    backgroundColor: "#fff",
    border: "1px solid #e4e4e4",
    borderRadius: "12px",
    padding: "16px 20px",
    marginBottom: "20px",
    fontFamily: "system-ui, sans-serif",
  },
  title: {
    fontSize: "13px",
    fontWeight: 600,
    color: "#555",
    margin: "0 0 10px 0",
  },
  row: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
    alignItems: "center",
    marginBottom: "10px",
  },
  input: {
    flex: "1 1 140px",
    minWidth: "120px",
    padding: "8px 12px",
    borderRadius: "8px",
    border: "1.5px solid #d4d4d4",
    fontSize: "14px",
    outline: "none",
  },
  button: {
    border: "1px solid #ccc",
    background: "#fff",
    borderRadius: "8px",
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: "13px",
    color: "#222",
  },
  primary: {
    border: "1px solid #4a7cf6",
    background: "#4a7cf6",
    color: "#fff",
  },
  chips: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
  },
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    padding: "4px 10px",
    borderRadius: "999px",
    background: "#f0f0f0",
    fontSize: "12.5px",
    color: "#444",
  },
  chipBtn: {
    border: "none",
    background: "transparent",
    cursor: "pointer",
    color: "#888",
    fontSize: "14px",
    lineHeight: 1,
    padding: 0,
  },
  error: {
    color: "#b00020",
    fontSize: "12.5px",
    marginTop: "6px",
  },
  muted: {
    color: "#999",
    fontSize: "12.5px",
  },
  fileInput: {
    fontSize: "13px",
  },
  review: {
    margin: "12px 0",
    border: "1px solid #eee",
    borderRadius: "8px",
    maxHeight: "280px",
    overflowY: "auto",
  },
  reviewRow: {
    display: "grid",
    gridTemplateColumns: "24px 110px 1fr 70px 80px 90px",
    gap: "8px",
    alignItems: "center",
    padding: "6px 10px",
    fontSize: "12.5px",
    borderBottom: "1px solid #f0f0f0",
  },
  reviewHead: {
    fontWeight: 600,
    color: "#666",
    background: "#fafafa",
    position: "sticky",
    top: 0,
  },
  status: {
    completed: { color: "#2e7d32" },
    in_progress: { color: "#b06000" },
    enrolled: { color: "#666" },
  },
};

function mergeRows(prev, incoming) {
  const byCode = new Map(prev.map((r) => [r.course_code, r]));
  for (const r of incoming) {
    byCode.set(r.course_code, r);
  }
  return [...byCode.values()].sort((a, b) =>
    a.course_code.localeCompare(b.course_code)
  );
}

/**
 * Manual taken-courses editor + transcript PDF import.
 * @param {{ onChange?: (codes: Set<string>) => void }} props
 */
export function TakenCoursesPanel({ onChange }) {
  const { user } = useAuth();
  const [rows, setRows] = useState([]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [parsed, setParsed] = useState(null);
  const [selected, setSelected] = useState(() => new Set());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!user?.id) {
        setRows([]);
        onChange?.(new Set());
        return;
      }
      const { data, error: err } = await fetchCompletedCourses(user.id);
      if (cancelled) return;
      if (err) {
        setError(err.message);
        return;
      }
      setRows(data);
      onChange?.(completedCodesSet(data));
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [user?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const codes = useMemo(() => completedCodesSet(rows), [rows]);

  async function handleAdd(e) {
    e.preventDefault();
    if (!user?.id || !draft.trim()) return;
    setBusy(true);
    setError(null);
    const { data, error: err } = await addCompletedCourse(user.id, {
      course_code: draft,
    });
    setBusy(false);
    if (err) {
      setError(err.message);
      return;
    }
    setDraft("");
    setRows((prev) => {
      const next = mergeRows(prev, [data]);
      onChange?.(completedCodesSet(next));
      return next;
    });
  }

  async function handleRemove(code) {
    if (!user?.id) return;
    setBusy(true);
    setError(null);
    const { error: err } = await removeCompletedCourse(user.id, code);
    setBusy(false);
    if (err) {
      setError(err.message);
      return;
    }
    setRows((prev) => {
      const next = prev.filter((r) => r.course_code !== code);
      onChange?.(completedCodesSet(next));
      return next;
    });
  }

  async function handlePdf(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setBusy(true);
    setError(null);
    setParsed(null);
    try {
      const result = await parseTranscriptPdf(file);
      const already = codes;
      const fresh = (result.courses || []).filter((c) => {
        const code = normalizeCourseCode(c.course_code);
        return code && !already.has(code);
      });
      const skipped = (result.courses || []).length - fresh.length;
      const pre = new Set(
        fresh.filter((c) => c.status === "completed").map((c) => c.course_code)
      );
      setParsed({
        ...result,
        courses: fresh,
        skipped,
      });
      setSelected(pre);
    } catch (err) {
      const msg = err?.message || "Could not parse PDF";
      if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
        setError(
          import.meta.env.VITE_TRANSCRIPT_API_URL
            ? "Could not reach the transcript parser. Check that the API is running."
            : "Start the parser: npm run transcript-api (port 8787)"
        );
      } else {
        setError(msg);
      }
    }
    setBusy(false);
  }

  function toggleCode(code) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  }

  async function confirmParsed() {
    if (!user?.id || !parsed?.courses?.length) return;
    const chosen = parsed.courses.filter((c) => selected.has(c.course_code));
    if (!chosen.length) {
      setError("Select at least one course to import");
      return;
    }
    setBusy(true);
    setError(null);
    const { data, error: err } = await addCompletedCourses(user.id, chosen);
    setBusy(false);
    if (err) {
      setError(err.message);
      return;
    }
    setParsed(null);
    setSelected(new Set());
    setRows((prev) => {
      const next = mergeRows(prev, data);
      onChange?.(completedCodesSet(next));
      return next;
    });
  }

  if (!user) return null;

  return (
    <div style={styles.wrap}>
      <p style={styles.title}>Courses you’ve completed</p>
      <div style={styles.row}>
        <label style={{ ...styles.button, cursor: busy ? "default" : "pointer" }}>
          Upload transcript PDF
          <input
            type="file"
            accept="application/pdf"
            onChange={handlePdf}
            disabled={busy}
            style={{ display: "none" }}
          />
        </label>
        <span style={styles.muted}>Unofficial UMich transcript</span>
      </div>

      {parsed && parsed.courses.length === 0 && (
        <p style={styles.muted}>
          No new courses
          {parsed.skipped
            ? ` — ${parsed.skipped} already saved from this transcript.`
            : "."}
        </p>
      )}

      {parsed?.courses?.length > 0 && (
        <>
          <p style={styles.muted}>
            {parsed.courses.length} new course
            {parsed.courses.length === 1 ? "" : "s"}
            {parsed.skipped
              ? ` (${parsed.skipped} already saved, hidden)`
              : ""}
            {" — "}
            completed are checked
          </p>
          <div style={styles.review}>
            <div style={{ ...styles.reviewRow, ...styles.reviewHead }}>
              <span />
              <span>Code</span>
              <span>Title</span>
              <span>Credits</span>
              <span>Term</span>
              <span>Status</span>
            </div>
            {parsed.courses.map((c) => (
              <label key={c.course_code} style={styles.reviewRow}>
                <input
                  type="checkbox"
                  checked={selected.has(c.course_code)}
                  onChange={() => toggleCode(c.course_code)}
                  disabled={busy}
                />
                <span>{c.course_code}</span>
                <span>{c.title || ""}</span>
                <span>{c.credits ?? ""}</span>
                <span>{c.term_completed || ""}</span>
                <span style={styles.status[c.status] || {}}>
                  {c.status.replace("_", " ")}
                  {c.grade ? ` (${c.grade})` : ""}
                </span>
              </label>
            ))}
          </div>
          <div style={styles.row}>
            <button
              type="button"
              style={{ ...styles.button, ...styles.primary }}
              onClick={confirmParsed}
              disabled={busy || selected.size === 0}
            >
              Import {selected.size} course{selected.size === 1 ? "" : "s"}
            </button>
            <button
              type="button"
              style={styles.button}
              onClick={() => {
                setParsed(null);
                setSelected(new Set());
              }}
              disabled={busy}
            >
              Cancel
            </button>
          </div>
        </>
      )}

      <form style={styles.row} onSubmit={handleAdd}>
        <input
          style={styles.input}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="e.g. EECS 280"
          disabled={busy}
        />
        <button
          type="submit"
          style={{ ...styles.button, ...styles.primary }}
          disabled={busy || !draft.trim()}
        >
          Add
        </button>
      </form>
      {rows.length === 0 ? (
        <p style={styles.muted}>None yet — upload a transcript or add a code.</p>
      ) : (
        <div style={styles.chips}>
          {[...codes].sort().map((code) => (
            <span key={code} style={styles.chip}>
              {code}
              <button
                type="button"
                style={styles.chipBtn}
                aria-label={`Remove ${code}`}
                onClick={() => handleRemove(code)}
                disabled={busy}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      {error && <p style={styles.error}>{error}</p>}
    </div>
  );
}
