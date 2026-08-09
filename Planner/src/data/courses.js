import data from "./courses.json";

const SEMESTER_MAP = {
  "2610": "Fall 2026",
  "2570": "Winter 2026",
  "2580": "Spring 2026",
  "2590": "Spring/Summer 2026",
  "2600": "Summer 2026",
};

function mapSemesters(courses) {
  if (!Array.isArray(courses)) return [];
  return courses.map(course => ({
    ...course,
    semester: SEMESTER_MAP[course.semester] || course.semester,
  }));
}

// Flatten all courses per major for filtering
export const COURSES_DATA = Object.fromEntries(
  Object.entries(data).map(([major, groups]) => [
    major,
    Object.fromEntries(
      Object.entries(groups).map(([group, courses]) => [
        group,
        mapSemesters(courses),
      ])
    ),
  ])
);

export const MAJORS = Object.keys(COURSES_DATA);

export const LEVELS = [
  { label: "All levels", value: "all" },
  { label: "Undergrad (100–499)", value: "undergrad" },
  { label: "100-level", value: "100" },
  { label: "200-level", value: "200" },
  { label: "300-level", value: "300" },
  { label: "400-level", value: "400" },
  { label: "500+", value: "500+" },
];

/** Catalog number band from a code like "MATH 215" or "EECS 281". */
export function getCourseLevel(code) {
  const m = String(code || "").match(/\b(\d{3})\b/);
  if (!m) return null;
  return Math.floor(Number(m[1]) / 100) * 100;
}

export function matchesLevelFilter(code, levelFilter) {
  if (!levelFilter || levelFilter === "all") return true;
  const level = getCourseLevel(code);
  if (level == null) return true;
  if (levelFilter === "undergrad") return level >= 100 && level <= 400;
  if (levelFilter === "500+") return level >= 500;
  return level === Number(levelFilter);
}

// Get all requirement groups for a major
export function getGroups(major) {
  return major ? ["All", ...Object.keys(COURSES_DATA[major])] : [];
}

// Get courses for a major, optionally filtered by group
export function getCourses(major, group) {
  if (!major) return [];
  if (!group || group === "All") {
    return Object.values(COURSES_DATA[major]).flat();
  }
  return COURSES_DATA[major][group] || [];
}

const semesterSet = new Set(
  Object.values(COURSES_DATA)
    .flatMap(groups => Object.values(groups).flat())
    .map(c => c.semester)
);
export const SEMESTERS = ["All semesters", ...Array.from(semesterSet).sort()];