import { useState, useMemo } from "react";
import { getCourses, getGroups, matchesLevelFilter } from "../data/courses";

export function useCourseFilter() {
    const [selectedMajor, setSelectedMajor] = useState("");
    const [selectedGroup, setSelectedGroup] = useState("All");
    const [selectedLevel, setSelectedLevel] = useState("undergrad");
    const [selectedSemester, setSelectedSemester] = useState("All semesters");
    const [searchQuery, setSearchQuery] = useState("");

    // Reset group when major changes
    function handleMajorChange(major) {
        setSelectedMajor(major);
        setSelectedGroup("All");
    }

    const groups = useMemo(() => getGroups(selectedMajor), [selectedMajor]);

    const filteredCourses = useMemo(() => {
        if (!selectedMajor) return [];

        let courses = getCourses(selectedMajor, selectedGroup);

        // Deduplicate by course code + semester (same code can appear in multiple groups)
        const seen = new Set();
        courses = courses.filter(c => {
            const key = `${c.code}|${c.termCode || c.semester}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
        });

        courses = courses.filter(c => matchesLevelFilter(c.code, selectedLevel));

        if (selectedSemester !== "All semesters") {
            courses = courses.filter(c => c.semester === selectedSemester);
        }

        if (searchQuery.trim()) {
            const q = searchQuery.trim().toLowerCase();
            courses = courses.filter(c =>
                c.code.toLowerCase().includes(q) ||
                c.title.toLowerCase().includes(q)
            );
        }

        return courses;
    }, [selectedMajor, selectedGroup, selectedLevel, selectedSemester, searchQuery]);

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
        filteredCourses,
        groupedCourses,
    };
}