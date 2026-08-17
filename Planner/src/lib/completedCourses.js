import { supabase } from "./supabase";
import { normalizeCourseCode } from "./completion";

/**
 * @typedef {{
 *   id?: number,
 *   course_code: string,
 *   title?: string | null,
 *   credits?: number | null,
 *   term_completed?: string | null,
 *   source?: string
 * }} CompletedCourse
 */

/** @param {string} studentId */
export async function fetchCompletedCourses(studentId) {
  if (!supabase || !studentId) return { data: [], error: null };
  const { data, error } = await supabase
    .from("student_completed_courses")
    .select("id, course_code, title, credits, term_completed, source")
    .eq("student_id", studentId)
    .order("course_code");
  return { data: data || [], error };
}

/**
 * @param {string} studentId
 * @param {{ course_code: string, title?: string, credits?: number, term_completed?: string }} input
 */
export async function addCompletedCourse(studentId, input) {
  if (!supabase || !studentId) {
    return { data: null, error: new Error("Not signed in") };
  }
  const code = normalizeCourseCode(input.course_code);
  if (!code) {
    return { data: null, error: new Error("Enter a course code like EECS 280") };
  }
  const row = {
    student_id: studentId,
    course_code: code,
    title: input.title || null,
    credits: input.credits ?? null,
    term_completed: input.term_completed || null,
    source: "manual",
  };
  const { data, error } = await supabase
    .from("student_completed_courses")
    .upsert(row, { onConflict: "student_id,course_code" })
    .select("id, course_code, title, credits, term_completed, source")
    .single();
  return { data, error };
}

/**
 * Upsert many transcript rows. source is 'pdf' (DB enum).
 * @param {string} studentId
 * @param {Array<{ course_code: string, title?: string, credits?: number, term_completed?: string }>} courses
 */
export async function addCompletedCourses(studentId, courses) {
  if (!supabase || !studentId) {
    return { data: [], error: new Error("Not signed in") };
  }
  const rows = [];
  const seen = new Set();
  for (const c of courses || []) {
    const code = normalizeCourseCode(c.course_code);
    if (!code || seen.has(code)) continue;
    seen.add(code);
    rows.push({
      student_id: studentId,
      course_code: code,
      title: c.title || null,
      credits: c.credits ?? null,
      term_completed: c.term_completed || null,
      source: "pdf",
    });
  }
  if (!rows.length) return { data: [], error: null };
  const { data, error } = await supabase
    .from("student_completed_courses")
    .upsert(rows, { onConflict: "student_id,course_code" })
    .select("id, course_code, title, credits, term_completed, source");
  return { data: data || [], error };
}

/** @param {string} studentId @param {string} courseCode */
export async function removeCompletedCourse(studentId, courseCode) {
  if (!supabase || !studentId) {
    return { error: new Error("Not signed in") };
  }
  const code = normalizeCourseCode(courseCode);
  const { error } = await supabase
    .from("student_completed_courses")
    .delete()
    .eq("student_id", studentId)
    .eq("course_code", code);
  return { error };
}

/** @param {CompletedCourse[]} rows */
export function completedCodesSet(rows) {
  const set = new Set();
  for (const r of rows || []) {
    const n = normalizeCourseCode(r.course_code);
    if (n) set.add(n);
  }
  return set;
}
