import { useState } from "react";
import { SectionRow } from "./SectionRow";
import { ChevronDownIcon } from "./Icons";
import { getOfferingPattern } from "../data/courses";

const SEMESTER_BADGE = {
  fall: {
    background: "#fff4e5",
    color: "#b06000",
    border: "1px solid #ffd699",
  },
  winter: {
    background: "#e8f0ff",
    color: "#2a52be",
    border: "1px solid #c0d0f8",
  },
  other: {
    background: "#f3f3f3",
    color: "#555",
    border: "1px solid #ddd",
  },
};

function getSemesterStyle(semester) {
  const s = String(semester || "").toLowerCase();
  if (s.startsWith("fall") || s.startsWith("fa")) return SEMESTER_BADGE.fall;
  if (s.startsWith("winter") || s.startsWith("wn")) return SEMESTER_BADGE.winter;
  return SEMESTER_BADGE.other;
}

const styles = {
  card: {
    border: "1px solid #e4e4e4",
    borderRadius: "10px",
    padding: "18px 20px",
    backgroundColor: "#fff",
  },
  header: {
    cursor: "pointer",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  meta: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    flexWrap: "wrap",
    marginBottom: "4px",
  },
  code: {
    fontWeight: 700,
    fontSize: "15.5px",
    color: "#1a1a1a",
  },
  credits: {
    fontSize: "13px",
    color: "#666",
  },
  semesterBadge: (semester) => ({
    fontSize: "12px",
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: "4px",
    ...getSemesterStyle(semester),
  }),
  sectionCount: {
    fontSize: "12.5px",
    color: "#888",
  },
  title: {
    fontSize: "15px",
    fontWeight: 500,
    color: "#222",
    marginBottom: "3px",
  },
  pattern: {
    fontSize: "12.5px",
    color: "#777",
    marginTop: "2px",
    fontFamily: "system-ui, sans-serif",
  },
  patternLabel: {
    color: "#999",
  },
  professors: {
    fontSize: "13px",
    color: "#777",
  },
  right: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginLeft: "16px",
    flexShrink: 0,
  },
  seats: {
    fontSize: "13.5px",
    color: "#555",
  },
  sectionsContainer: {
    marginTop: "14px",
    display: "flex",
    flexDirection: "column",
    gap: "8px",
  },
};

export function CourseCard({ course, major }) {
  const [expanded, setExpanded] = useState(false);
  const semesterLabel = course.semester;
  const pattern = getOfferingPattern(major, course.code);

  return (
    <div style={styles.card}>
      <div style={styles.header} onClick={() => setExpanded((prev) => !prev)}>
        <div>
          <div style={styles.meta}>
            <span style={styles.code}>{course.code}</span>
            <span style={styles.credits}>{course.credits} credits</span>
            <span style={styles.semesterBadge(semesterLabel)}>{semesterLabel}</span>
            <span style={styles.sectionCount}>{course.sections} sections</span>
          </div>
          <div style={styles.title}>{course.title}</div>
          {pattern.length > 0 && (
            <div style={styles.pattern}>
              <span style={styles.patternLabel}>Offered: </span>
              {pattern.join(" · ")}
            </div>
          )}
          <div style={styles.professors}>{course.instructor || ""}</div>
        </div>
        <div style={styles.right}>
          <span style={styles.seats}>{course.seats} seats</span>
          <span
            style={{
              color: "#999",
              transition: "transform 0.2s",
              transform: expanded ? "rotate(180deg)" : "rotate(0deg)",
              display: "flex",
            }}
          >
            <ChevronDownIcon />
          </span>
        </div>
      </div>

      {expanded && (
        <div style={styles.sectionsContainer}>
          {course.sectionDetails.map((sec) => (
            <SectionRow key={sec.id} section={sec} />
          ))}
        </div>
      )}
    </div>
  );
}
