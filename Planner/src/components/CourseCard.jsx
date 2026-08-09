import { useState } from "react";
import { SectionRow } from "./SectionRow";
import { TrendIcon, ChevronDownIcon } from "./Icons";

const SEMESTER_MAP = {
  "2420": "Fall 2026",
  "2510": "Winter 2027",
  "2490": "Spring/Summer 2026",
};

function formatSemester(termCode) {
  return SEMESTER_MAP[termCode] || termCode;
}

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
};

function getSemesterStyle(semester) {
  return semester.toLowerCase().startsWith("fall")
    ? SEMESTER_BADGE.fall
    : SEMESTER_BADGE.winter;
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

export function CourseCard({ course }) {
  const [expanded, setExpanded] = useState(false);
  const semesterLabel = formatSemester(course.semester);

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