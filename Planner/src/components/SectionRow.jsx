const styles = {
  row: {
    border: "1px solid #e8e8e8",
    borderRadius: "8px",
    padding: "12px 16px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  left: {},
  header: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "4px",
  },
  sectionId: {
    fontWeight: 600,
    fontSize: "13.5px",
    color: "#222",
  },
  dot: {
    color: "#999",
    fontSize: "13px",
  },
  prof: {
    fontSize: "13px",
    color: "#555",
  },
  time: {
    fontSize: "13px",
    color: "#555",
  },
  room: {
    fontSize: "12.5px",
    color: "#999",
    marginTop: "2px",
  },
  seats: {
    fontSize: "13px",
    color: "#666",
    whiteSpace: "nowrap",
  },
};

/**
 * @param {{ id: string, prof: string, time: string, room: string, seats: number }} section
 */
export function SectionRow({ section }) {
  return (
    <div style={styles.row}>
      <div style={styles.left}>
        <div style={styles.header}>
          <span style={styles.sectionId}>Section {section.id}</span>
          <span style={styles.dot}>·</span>
          <span style={styles.prof}>{section.prof}</span>
        </div>
        <div style={styles.time}>{section.time}</div>
        <div style={styles.room}>{section.room}</div>
      </div>
      <span style={styles.seats}>{section.seats} seats</span>
    </div>
  );
}
