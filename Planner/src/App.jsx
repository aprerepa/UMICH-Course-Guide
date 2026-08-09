import { FilterBar } from "./components/FilterBar";
import { CourseList } from "./components/CourseList";
import { useCourseFilter } from "./hooks/useCourseFilter";

const styles = {
  page: {
    fontFamily: "'Georgia', 'Times New Roman', serif",
    backgroundColor: "#f5f5f3",
    minHeight: "100vh",
    padding: "32px 40px",
    boxSizing: "border-box",
  },
  inner: {
    width: "100%",
  },
  heading: {
    fontSize: "26px",
    fontWeight: 700,
    color: "#1a1a1a",
    margin: "0 0 4px 0",
    fontFamily: "'Georgia', serif",
  },
  subheading: {
    fontSize: "14px",
    color: "#888",
    margin: "0 0 28px 0",
    fontFamily: "system-ui, sans-serif",
  },
};

export default function App() {
  const {
    selectedMajor,
    setSelectedMajor,
    selectedGroup,
    setSelectedGroup,
    groups,
    selectedLevel,
    setSelectedLevel,
    selectedSemester,
    setSelectedSemester,
    searchQuery,
    setSearchQuery,
    filteredCourses,
    groupedCourses,
  } = useCourseFilter();

  return (
    <div style={styles.page}>
      <div style={styles.inner}>
        <h1 style={styles.heading}>UMich Course Guide</h1>
        <p style={styles.subheading}>Filter courses by major and view historic offerings</p>

        <FilterBar
          selectedMajor={selectedMajor}
          onMajorChange={setSelectedMajor}
          selectedGroup={selectedGroup}
          onGroupChange={setSelectedGroup}
          groups={groups}
          selectedLevel={selectedLevel}
          onLevelChange={setSelectedLevel}
          selectedSemester={selectedSemester}
          onSemesterChange={setSelectedSemester}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
        />

        <CourseList
          majorSelected={!!selectedMajor}
          totalCount={filteredCourses.length}
          groupedCourses={groupedCourses}
        />
      </div>
    </div>
  );
}