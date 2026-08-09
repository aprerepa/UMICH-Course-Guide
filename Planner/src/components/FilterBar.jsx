import { useState } from "react";
import { Dropdown } from "./Dropdown";
import { SearchIcon } from "./Icons";
import { MAJORS, SEMESTERS, LEVELS } from "../data/courses";

const majorOptions = [
  { label: "Choose a major...", value: "" },
  ...MAJORS.map((m) => ({ label: m, value: m })),
];

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
};

export function FilterBar({
  selectedMajor,
  onMajorChange,
  selectedGroup,
  onGroupChange,
  groups,
  selectedLevel,
  onLevelChange,
  selectedSemester,
  onSemesterChange,
  searchQuery,
  onSearchChange,
}) {
  const [openDropdown, setOpenDropdown] = useState(null);

  const toggle = (name) => setOpenDropdown((prev) => (prev === name ? null : name));

  const groupOptions = (groups || []).map((g) => ({ label: g, value: g }));

  return (
    <div style={styles.container} onClick={() => setOpenDropdown(null)}>
      {/* Major */}
      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Select Major</label>
        <Dropdown
          value={selectedMajor}
          onChange={(v) => { onMajorChange(v); setOpenDropdown(null); }}
          options={majorOptions}
          placeholder="Choose a major..."
          isOpen={openDropdown === "major"}
          onToggle={() => toggle("major")}
        />
      </div>

      {/* Requirement Group */}
      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Requirement Group</label>
        <Dropdown
          value={selectedGroup}
          onChange={(v) => { onGroupChange(v); setOpenDropdown(null); }}
          options={groupOptions}
          placeholder="All"
          isOpen={openDropdown === "group"}
          onToggle={() => toggle("group")}
        />
      </div>

      {/* Course Level */}
      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Course Level</label>
        <Dropdown
          value={selectedLevel}
          onChange={(v) => { onLevelChange(v); setOpenDropdown(null); }}
          options={levelOptions}
          placeholder="Undergrad (100–499)"
          isOpen={openDropdown === "level"}
          onToggle={() => toggle("level")}
        />
      </div>

      {/* Semester */}
      <div style={styles.fieldWrapper} onClick={(e) => e.stopPropagation()}>
        <label style={styles.label}>Select Semester</label>
        <Dropdown
          value={selectedSemester}
          onChange={(v) => { onSemesterChange(v); setOpenDropdown(null); }}
          options={semesterOptions}
          placeholder="All semesters"
          isOpen={openDropdown === "semester"}
          onToggle={() => toggle("semester")}
        />
      </div>

      {/* Search */}
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