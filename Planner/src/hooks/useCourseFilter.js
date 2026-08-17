import { useState, useMemo, useEffect } from "react";
import {
  getCourses,
  getGroups,
  matchesLevelFilter,
  MAJORS,
  COURSES_DATA,
} from "../data/courses";
import { getGroupRules, getRulesForMajor } from "../data/rulesCatalog";
import {
  getMajorConfig,
  groupHitCodesFromConfig,
} from "../data/majorConfigs";
import { isGroupComplete, normalizeCourseCode } from "../lib/completion";
import { useAuth } from "../context/AuthContext";

function buildCreditMap(major) {
  const map = {};
  for (const courses of Object.values(COURSES_DATA[major] || {})) {
    for (const c of courses) {
      const code = normalizeCourseCode(c.code);
      if (code && typeof c.credits === "number") map[code] = c.credits;
    }
  }
  return map;
}

function findGroupRule(groupRules, groupName) {
  if (!groupRules || !groupName) return null;
  if (groupRules[groupName]) return groupRules[groupName];
  const lower = groupName.toLowerCase();
  for (const [key, rule] of Object.entries(groupRules)) {
    if (key.toLowerCase() === lower) return rule;
  }
  return null;
}

export function useCourseFilter() {
  const { user, guest, programs } = useAuth();
  const [selectedMajor, setSelectedMajor] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("All");
  const [selectedLevel, setSelectedLevel] = useState("undergrad");
  const [selectedSemester, setSelectedSemester] = useState("All semesters");
  const [searchQuery, setSearchQuery] = useState("");
  /** @type {[Set<string>, Function]} */
  const [takenCodes, setTakenCodes] = useState(() => new Set());

  const availableMajors = useMemo(() => {
    if (guest || !user) {
      return MAJORS;
    }
    const names = programs.map((p) => p.display_name).filter(Boolean);
    const unique = [];
    const seen = new Set();
    for (const name of names) {
      if (seen.has(name)) continue;
      seen.add(name);
      unique.push(name);
    }
    return unique;
  }, [guest, user, programs]);

  useEffect(() => {
    if (!selectedMajor) {
      if (availableMajors.length === 1) {
        setSelectedMajor(availableMajors[0]);
        setSelectedGroup("All");
      }
      return;
    }
    if (!availableMajors.includes(selectedMajor)) {
      setSelectedMajor(availableMajors.length === 1 ? availableMajors[0] : "");
      setSelectedGroup("All");
    }
  }, [availableMajors, selectedMajor]);

  function handleMajorChange(major) {
    setSelectedMajor(major);
    setSelectedGroup("All");
  }

  const configIdForMajor = useMemo(() => {
    if (!selectedMajor) return null;
    const prog = programs.find((p) => p.display_name === selectedMajor);
    return prog?.config_id || null;
  }, [programs, selectedMajor]);

  const majorConfig = useMemo(
    () =>
      getMajorConfig({
        configId: configIdForMajor,
        displayName: selectedMajor,
      }),
    [configIdForMajor, selectedMajor]
  );

  const rulesDoc = useMemo(
    () =>
      getRulesForMajor({
        configId: configIdForMajor || majorConfig?.id,
        displayName: selectedMajor,
      }),
    [configIdForMajor, majorConfig, selectedMajor]
  );

  const groupRules = useMemo(() => getGroupRules(rulesDoc), [rulesDoc]);

  const creditByCode = useMemo(
    () => buildCreditMap(selectedMajor),
    [selectedMajor]
  );

  const groups = useMemo(() => getGroups(selectedMajor), [selectedMajor]);

  const completedGroups = useMemo(() => {
    const done = new Set();
    if (!selectedMajor || takenCodes.size === 0) return done;
    for (const groupName of groups) {
      if (groupName === "All") continue;
      const rule = findGroupRule(groupRules, groupName);
      if (!rule) continue;
      // Eligible = major config lists / open bands, NOT current-term SOC offerings
      const hits = majorConfig
        ? groupHitCodesFromConfig(majorConfig, groupName, takenCodes)
        : [];
      const credits = { ...creditByCode };
      for (const code of hits) {
        if (credits[code] == null) credits[code] = 3;
      }
      const result = isGroupComplete(rule, {
        takenCodes,
        groupHitCodes: hits,
        creditByCode: credits,
      });
      if (result.complete) done.add(groupName);
    }
    return done;
  }, [
    selectedMajor,
    groups,
    groupRules,
    takenCodes,
    creditByCode,
    majorConfig,
  ]);

  const filteredCourses = useMemo(() => {
    if (!selectedMajor) return [];

    let courses = getCourses(selectedMajor, selectedGroup);

    const seen = new Set();
    courses = courses.filter((c) => {
      const key = `${c.code}|${c.termCode || c.semester}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });

    if (takenCodes.size > 0) {
      courses = courses.filter(
        (c) => !takenCodes.has(normalizeCourseCode(c.code))
      );
    }

    courses = courses.filter((c) => matchesLevelFilter(c.code, selectedLevel));

    if (selectedSemester !== "All semesters") {
      courses = courses.filter((c) => c.semester === selectedSemester);
    }

    if (searchQuery.trim()) {
      const q = searchQuery.trim().toLowerCase();
      courses = courses.filter(
        (c) =>
          c.code.toLowerCase().includes(q) || c.title.toLowerCase().includes(q)
      );
    }

    return courses;
  }, [
    selectedMajor,
    selectedGroup,
    selectedLevel,
    selectedSemester,
    searchQuery,
    takenCodes,
  ]);

  const groupedCourses = useMemo(() => {
    if (selectedSemester !== "All semesters") {
      return { [selectedSemester]: filteredCourses };
    }
    return filteredCourses.reduce((acc, course) => {
      if (!acc[course.semester]) acc[course.semester] = [];
      acc[course.semester].push(course);
      return acc;
    }, {});
  }, [filteredCourses, selectedSemester]);

  return {
    selectedMajor,
    setSelectedMajor: handleMajorChange,
    selectedGroup,
    setSelectedGroup,
    selectedLevel,
    setSelectedLevel,
    selectedSemester,
    setSelectedSemester,
    searchQuery,
    setSearchQuery,
    groups,
    completedGroups,
    filteredCourses,
    groupedCourses,
    availableMajors,
    personalized: Boolean(user) && !guest,
    takenCodes,
    setTakenCodes,
  };
}
