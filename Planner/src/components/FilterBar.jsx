import { useState } from "react";
import { Dropdown } from "./Dropdown";
import { SearchIcon } from "./Icons";
import { SEMESTERS, LEVELS } from "../data/courses";

const semesterOptions = SEMESTERS.map((s) => ({ label: s, value: s }));
const levelOptions = LEVELS;

const styles = {
  container: {
    backgroundColor: "#fff",
    border: "1px solid #e4e4e4",
    borderRadius: "12px",
    padding: "20px 24px",
    marginBottom: "24px",
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr 1fr",
    gap: "20px",
    alignItems: "end",
  },
  searchField: {
    gridColumn: "1 / -1",
  },
  fieldWrapper: {},
  label: {
    display: "block",
    fontSize: "12.5px",
    fontWeight: 600,
    color: "#555",
    marginBottom: "6px",
    fontFamily: "system-ui, sans-serif",
  },
  searchWrapper: {
    position: "relative",
  },
  searchIcon: {
    position: "absolute",
    left: "12px",
    top: "50%",
    transform: "translateY(-50%)",
    color: "#aaa",
    pointerEvents: "none",
  },
  searchInput: (active) => ({
    width: "100%",
    padding: "10px 14px 10px 34px",
    borderRadius: "8px",
    border: active ? "2px solid #4a7cf6" : "1.5px solid #d4d4d4",
    fontSize: "14px",
    color: "#222",
    outline: "none",
    boxSizing: "border-box",
    fontFamily: "system-ui, sans-serif",
    backgroundColor: "#fff",
  }),
  hint: {
    gridColumn: "1 / -1",
    fontSize: "12.5px",
    color: "#888",
    fontFamily: "system-ui, sans-serif",
    marginTop: "-8px",
  },
};

export function FilterBar({
  selectedMajor,
  onMajorChange,
  selectedGroup,
  onGroupChange,
  groups,
  completedGroups,
  selectedLevel,
  onLevelChange,
  selectedSemester,
  onSemesterChange,
  searchQuery,
  onSearchChange,
  availableMajors = [],
  personalized = false,
}) {
  const [openDropdown, setOpenDropdown] = useState(null);

  const toggle = (name) =>
    setOpenDropdown((prev) => (prev === name ? null : name));

  const majorOptions = [
    {
      label: personalized ? "Choose one of your majors..." : "Choose a major...",
      value: "",
    },
    ...availableMajors.map((m) => ({ label: m, value: m })),
  ];

  const groupOptions = (groups || []).map((g) => ({
    label: g,
    value: g,
    muted: g !== "All" && completedGroups?.has?.(g),
  }));

  return (
    <div style={styles.container} onClick={() => setOpenDropdown(null)}>
      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Select Major</label>
        <Dropdown
          value={selectedMajor}
          onChange={(v) => {
            onMajorChange(v);
            setOpenDropdown(null);
          }}
          options={majorOptions}
          placeholder={
            personalized ? "Choose one of your majors..." : "Choose a major..."
          }
          isOpen={openDropdown === "major"}
          onToggle={() => toggle("major")}
        />
      </div>

      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Requirement Group</label>
        <Dropdown
          value={selectedGroup}
          onChange={(v) => {
            onGroupChange(v);
            setOpenDropdown(null);
          }}
          options={groupOptions}
          placeholder="All"
          isOpen={openDropdown === "group"}
          onToggle={() => toggle("group")}
        />
      </div>

      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Course Level</label>
        <Dropdown
          value={selectedLevel}
          onChange={(v) => {
            onLevelChange(v);
            setOpenDropdown(null);
          }}
          options={levelOptions}
          placeholder="Undergrad (100–499)"
          isOpen={openDropdown === "level"}
          onToggle={() => toggle("level")}
        />
      </div>

      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Select Semester</label>
        <Dropdown
          value={selectedSemester}
          onChange={(v) => {
            onSemesterChange(v);
            setOpenDropdown(null);
          }}
          options={semesterOptions}
          placeholder="All semesters"
          isOpen={openDropdown === "semester"}
          onToggle={() => toggle("semester")}
        />
      </div>

      {personalized && (
        <div style={styles.hint}>
          Showing only majors you selected at signup
          {availableMajors.length === 0 ? " — none saved yet." : "."}
          {completedGroups?.size
            ? " Completed requirement groups stay in the list, marked as done."
            : ""}
        </div>
      )}

      <div style={{ ...styles.fieldWrapper, ...styles.searchField }}>
        <label style={styles.label}>Search Courses</label>
        <div style={styles.searchWrapper}>
          <span style={styles.searchIcon}>
            <SearchIcon />
          </span>
          <input
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by code or title..."
            style={styles.searchInput(!!searchQuery)}
          />
        </div>
      </div>
    </div>
  );
}
