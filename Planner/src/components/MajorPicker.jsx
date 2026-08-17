import { useMemo, useState } from "react";
import { MAJOR_OPTIONS } from "../data/majorCatalog";

const styles = {
  box: {
    border: "1px solid #ddd",
    borderRadius: "8px",
    fontFamily: "system-ui, sans-serif",
    overflow: "hidden",
    background: "#fff",
  },
  search: {
    width: "100%",
    boxSizing: "border-box",
    border: "none",
    borderBottom: "1px solid #eee",
    padding: "10px 12px",
    fontSize: "14px",
    outline: "none",
  },
  list: {
    maxHeight: "280px",
    overflowY: "auto",
  },
  row: {
    display: "flex",
    alignItems: "flex-start",
    gap: "8px",
    padding: "8px 12px",
    fontSize: "13px",
    color: "#333",
    cursor: "pointer",
    borderBottom: "1px solid #f3f3f3",
  },
  chips: {
    display: "flex",
    flexWrap: "wrap",
    gap: "6px",
    padding: "8px 10px",
    borderBottom: "1px solid #eee",
    minHeight: "20px",
  },
  chip: {
    display: "inline-flex",
    alignItems: "center",
    gap: "6px",
    background: "#f0f0ee",
    borderRadius: "999px",
    padding: "4px 10px",
    fontSize: "12px",
    color: "#333",
  },
  chipX: {
    border: "none",
    background: "transparent",
    cursor: "pointer",
    padding: 0,
    fontSize: "14px",
    lineHeight: 1,
    color: "#666",
  },
  muted: {
    textAlign: "center",
    fontSize: "13px",
    color: "#888",
    padding: "12px",
    fontFamily: "system-ui, sans-serif",
  },
};

/**
 * Searchable multi-select for catalog majors.
 * @param {string[]} selectedIds
 * @param {(id: string) => void} onToggle
 */
export function MajorPicker({ selectedIds, onToggle }) {
  const [query, setQuery] = useState("");

  const selectedMajors = useMemo(
    () => MAJOR_OPTIONS.filter((m) => selectedIds.includes(m.id)),
    [selectedIds]
  );

  const filteredMajors = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return MAJOR_OPTIONS;
    return MAJOR_OPTIONS.filter((m) =>
      m.displayName.toLowerCase().includes(q)
    );
  }, [query]);

  return (
    <div style={styles.box}>
      {selectedMajors.length > 0 && (
        <div style={styles.chips}>
          {selectedMajors.map((m) => (
            <span key={m.id} style={styles.chip}>
              {m.displayName}
              <button
                type="button"
                style={styles.chipX}
                aria-label={`Remove ${m.displayName}`}
                onClick={() => onToggle(m.id)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
      <input
        style={styles.search}
        type="search"
        placeholder="Search majors…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        aria-label="Search majors"
      />
      <div style={styles.list}>
        {filteredMajors.map((m) => {
          const checked = selectedIds.includes(m.id);
          return (
            <label key={m.id} style={styles.row}>
              <input
                type="checkbox"
                checked={checked}
                onChange={() => onToggle(m.id)}
              />
              <span>{m.displayName}</span>
            </label>
          );
        })}
        {filteredMajors.length === 0 && (
          <div style={styles.muted}>No majors match that search.</div>
        )}
      </div>
    </div>
  );
}

export function programsFromIds(selectedIds) {
  return MAJOR_OPTIONS.filter((m) => selectedIds.includes(m.id)).map((m) => ({
    config_id: m.id,
    display_name: m.displayName,
    program_type: m.programType,
  }));
}
