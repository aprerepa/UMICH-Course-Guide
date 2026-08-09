import { CourseCard } from "./CourseCard";
import { CalendarIcon, CalendarEmptyIcon } from "./Icons";

const styles = {
  container: (hasContent) => ({
    backgroundColor: "#fff",
    border: "1px solid #e4e4e4",
    borderRadius: "12px",
    padding: hasContent ? "24px" : "0",
    minHeight: "200px",
  }),
  emptyState: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    padding: "72px 24px",
    gap: "12px",
  },
  emptyIcon: {
    color: "#c8c8c8",
  },
  emptyTitle: {
    fontSize: "16px",
    fontWeight: 600,
    color: "#555",
    margin: 0,
    fontFamily: "system-ui, sans-serif",
  },
  emptySubtitle: {
    fontSize: "14px",
    color: "#999",
    margin: 0,
    textAlign: "center",
    maxWidth: 340,
    fontFamily: "system-ui, sans-serif",
  },
  semesterGroup: {
    marginBottom: "28px",
  },
  groupHeader: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
    marginBottom: "14px",
  },
  groupIcon: {
    color: "#888",
  },
  groupTitle: {
    fontWeight: 700,
    fontSize: "16px",
    color: "#222",
    fontFamily: "system-ui, sans-serif",
  },
  groupCount: {
    fontSize: "14px",
    color: "#aaa",
    fontFamily: "system-ui, sans-serif",
  },
  cardList: {
    display: "flex",
    flexDirection: "column",
    gap: "10px",
  },
};

function EmptyState() {
  return (
    <div style={styles.emptyState}>
      <div style={styles.emptyIcon}>
        <CalendarEmptyIcon />
      </div>
      <p style={styles.emptyTitle}>Select a major to view courses</p>
      <p style={styles.emptySubtitle}>
        Choose your major and semester from the dropdowns above to see course
        offerings and historic patterns.
      </p>
    </div>
  );
}

function NoResults() {
  return (
    <div style={styles.emptyState}>
      <p style={styles.emptyTitle}>No courses found</p>
      <p style={styles.emptySubtitle}>
        Try adjusting your filters or search query.
      </p>
    </div>
  );
}

function SemesterGroup({ semester, courses }) {
  return (
    <div style={styles.semesterGroup}>
      <div style={styles.groupHeader}>
        <span style={styles.groupIcon}>
          <CalendarIcon />
        </span>
        <span style={styles.groupTitle}>{semester}</span>
        <span style={styles.groupCount}>
          ({courses.length} course{courses.length !== 1 ? "s" : ""})
        </span>
      </div>
      <div style={styles.cardList}>
        {courses.map((course, i) => (
          <CourseCard key={`${course.code}-${i}`} course={course} />
        ))}
      </div>
    </div>
  );
}

/**
 * @param {boolean} majorSelected    - Whether a major has been chosen
 * @param {number}  totalCount       - Total filtered courses across all semesters
 * @param {object}  groupedCourses   - { [semester]: Course[] }
 * @param {Function} onDismissDropdowns - Callback to close any open dropdowns on click
 */
export function CourseList({ majorSelected, totalCount, groupedCourses, onDismissDropdowns }) {
  const hasContent = majorSelected && totalCount > 0;

  return (
    <div style={styles.container(hasContent)} onClick={onDismissDropdowns}>
      {!majorSelected ? (
        <EmptyState />
      ) : totalCount === 0 ? (
        <NoResults />
      ) : (
        Object.entries(groupedCourses).map(([semester, courses]) => (
          <SemesterGroup key={semester} semester={semester} courses={courses} />
        ))
      )}
    </div>
  );
}
