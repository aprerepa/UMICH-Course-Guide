import { FilterBar } from "./components/FilterBar";
import { CourseList } from "./components/CourseList";
import { GuideHeader } from "./components/GuideHeader";
import { LoginPage } from "./components/LoginPage";
import { SettingsPage } from "./components/SettingsPage";
import { TakenCoursesPanel } from "./components/TakenCoursesPanel";
import { useCourseFilter } from "./hooks/useCourseFilter";
import { useAuth } from "./context/AuthContext";
import { useState } from "react";
import { Analytics } from "@vercel/analytics/react";

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
  centered: {
    fontFamily: "system-ui, sans-serif",
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "#888",
    backgroundColor: "#f5f5f3",
  },
};

function CourseGuide() {
  const { user } = useAuth();
  const [page, setPage] = useState("guide");
  const {
    selectedMajor,
    setSelectedMajor,
    selectedGroup,
    setSelectedGroup,
    groups,
    completedGroups,
    selectedLevel,
    setSelectedLevel,
    selectedSemester,
    setSelectedSemester,
    searchQuery,
    setSearchQuery,
    filteredCourses,
    groupedCourses,
    availableMajors,
    personalized,
    setTakenCodes,
  } = useCourseFilter();

  return (
    <div style={styles.page}>
      <div style={styles.inner}>
        <GuideHeader page={page} onNavigate={setPage} />
        {page === "settings" ? (
          <>
            <h1 style={styles.heading}>Settings</h1>
            <p style={styles.subheading}>Account and declared programs</p>
            <SettingsPage onBack={() => setPage("guide")} />
          </>
        ) : (
          <>
            <h1 style={styles.heading}>UMich Course Guide</h1>
            <p style={styles.subheading}>
              Filter courses by major and view historic offerings
            </p>

            {user && <TakenCoursesPanel onChange={setTakenCodes} />}

            <FilterBar
              selectedMajor={selectedMajor}
              onMajorChange={setSelectedMajor}
              selectedGroup={selectedGroup}
              onGroupChange={setSelectedGroup}
              groups={groups}
              completedGroups={completedGroups}
              selectedLevel={selectedLevel}
              onLevelChange={setSelectedLevel}
              selectedSemester={selectedSemester}
              onSemesterChange={setSelectedSemester}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              availableMajors={availableMajors}
              personalized={personalized}
            />

            <CourseList
              majorSelected={!!selectedMajor}
              major={selectedMajor}
              totalCount={filteredCourses.length}
              groupedCourses={groupedCourses}
            />
          </>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const { loading, inApp } = useAuth();

  if (loading) {
    return <div style={styles.centered}>Loading…</div>;
  }

  if (!inApp) {
    return <LoginPage />;
  }

  return (
    <>
      <CourseGuide />
      <Analytics />
    </>
  );
}