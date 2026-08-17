import { useEffect, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { MajorPicker, programsFromIds } from "./MajorPicker";
import { replaceStudentPrograms } from "../lib/studentPrograms";
import { deleteOwnAccount } from "../lib/deleteAccount";

const CONFIRM_PHRASE = "delete my account";

const styles = {
  page: {
    fontFamily: "system-ui, sans-serif",
    minHeight: "calc(100vh - 80px)",
    display: "flex",
    flexDirection: "column",
    gap: "24px",
  },
  section: {
    backgroundColor: "#fff",
    border: "1px solid #e4e4e4",
    borderRadius: "12px",
    padding: "24px 28px",
    width: "100%",
    boxSizing: "border-box",
  },
  heading: {
    fontSize: "16px",
    fontWeight: 700,
    color: "#1a1a1a",
    margin: "0 0 6px 0",
  },
  label: {
    fontSize: "12px",
    fontWeight: 600,
    color: "#888",
    marginBottom: "4px",
  },
  value: {
    fontSize: "15px",
    color: "#222",
    margin: "0 0 0 0",
    wordBreak: "break-all",
  },
  muted: {
    fontSize: "13.5px",
    color: "#888",
    margin: "0 0 14px 0",
    lineHeight: 1.45,
  },
  row: {
    display: "flex",
    gap: "8px",
    flexWrap: "wrap",
    marginTop: "14px",
  },
  button: {
    border: "1px solid #ccc",
    background: "#fff",
    borderRadius: "8px",
    padding: "8px 14px",
    cursor: "pointer",
    fontSize: "13px",
    color: "#222",
    fontFamily: "system-ui, sans-serif",
  },
  primary: {
    border: "1px solid #1a1a1a",
    background: "#1a1a1a",
    color: "#fff",
  },
  danger: {
    border: "1px solid #b00020",
    background: "#b00020",
    color: "#fff",
  },
  dangerZone: {
    border: "1px solid #f0c0c0",
    background: "#fff8f8",
  },
  dangerTitle: {
    fontSize: "16px",
    fontWeight: 700,
    color: "#b00020",
    margin: "0 0 6px 0",
  },
  input: {
    width: "100%",
    maxWidth: 420,
    boxSizing: "border-box",
    border: "1px solid #ddd",
    borderRadius: "8px",
    padding: "10px 12px",
    fontSize: "14px",
    fontFamily: "system-ui, sans-serif",
  },
  error: {
    color: "#b00020",
    fontSize: "13px",
    marginTop: "10px",
  },
  ok: {
    color: "#2a7a3a",
    fontSize: "13px",
    marginTop: "10px",
  },
  grow: {
    flex: 1,
  },
};

export function SettingsPage({ onBack }) {
  const { user, programs, reloadPrograms, signOut } = useAuth();
  const [selectedIds, setSelectedIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);
  const [confirmText, setConfirmText] = useState("");
  const [deleteError, setDeleteError] = useState(null);

  useEffect(() => {
    setSelectedIds((programs || []).map((p) => p.config_id));
  }, [programs]);

  function toggleMajor(id) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function saveMajors() {
    if (!user?.id) return;
    if (selectedIds.length === 0) {
      setError("Select at least one major.");
      setMessage(null);
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    const { error: err } = await replaceStudentPrograms(
      user.id,
      programsFromIds(selectedIds)
    );
    setBusy(false);
    if (err) {
      setError(err.message);
      return;
    }
    await reloadPrograms?.();
    setMessage("Majors saved.");
  }

  async function handleDelete() {
    if (!user?.id) return;
    if (confirmText.trim().toLowerCase() !== CONFIRM_PHRASE) {
      setDeleteError(`Type “${CONFIRM_PHRASE}” to confirm.`);
      return;
    }
    setBusy(true);
    setDeleteError(null);
    const { error: err } = await deleteOwnAccount(user.id);
    if (err) {
      setBusy(false);
      setDeleteError(err.message);
      return;
    }
    await signOut();
  }

  return (
    <div style={styles.page}>
      <section style={styles.section}>
        <h2 style={styles.heading}>Account</h2>
        <div style={styles.label}>Email</div>
        <p style={styles.value}>{user?.email || "—"}</p>
      </section>

      <section style={{ ...styles.section, ...styles.grow }}>
        <h2 style={styles.heading}>Majors</h2>
        <p style={styles.muted}>
          Add or remove programs. The course guide dropdown will only show what
          you save here.
        </p>
        <MajorPicker selectedIds={selectedIds} onToggle={toggleMajor} />
        <div style={styles.row}>
          <button
            type="button"
            style={{ ...styles.button, ...styles.primary }}
            onClick={saveMajors}
            disabled={busy}
          >
            Save majors
          </button>
          <button type="button" style={styles.button} onClick={onBack} disabled={busy}>
            Back to guide
          </button>
        </div>
        {error && <p style={styles.error}>{error}</p>}
        {message && <p style={styles.ok}>{message}</p>}
      </section>

      <section style={{ ...styles.section, ...styles.dangerZone }}>
        <h2 style={styles.dangerTitle}>Delete account</h2>
        <p style={styles.muted}>
          This permanently deletes your profile, declared majors, completed
          courses, transcript records, and group overrides. It cannot be undone.
        </p>
        <p style={styles.muted}>
          Type <strong>{CONFIRM_PHRASE}</strong> to confirm.
        </p>
        <input
          style={styles.input}
          value={confirmText}
          onChange={(e) => setConfirmText(e.target.value)}
          placeholder={CONFIRM_PHRASE}
          disabled={busy}
          autoComplete="off"
        />
        <div style={styles.row}>
          <button
            type="button"
            style={{ ...styles.button, ...styles.danger }}
            onClick={handleDelete}
            disabled={busy || confirmText.trim().toLowerCase() !== CONFIRM_PHRASE}
          >
            Delete my account
          </button>
        </div>
        {deleteError && <p style={styles.error}>{deleteError}</p>}
      </section>
    </div>
  );
}
