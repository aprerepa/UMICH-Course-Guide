import { supabase } from "../lib/supabase";

const PENDING_KEY = "courseGuidePendingPrograms";

/** @typedef {{ config_id: string, display_name: string, program_type: string }} ProgramRow */

export function stashPendingPrograms(programs) {
  try {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(programs));
  } catch {
    /* ignore */
  }
}

export function readPendingPrograms() {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

export function clearPendingPrograms() {
  try {
    sessionStorage.removeItem(PENDING_KEY);
  } catch {
    /* ignore */
  }
}

/**
 * Upsert declared programs for the signed-in user.
 * @param {string} studentId
 * @param {ProgramRow[]} programs
 */
export async function saveStudentPrograms(studentId, programs) {
  if (!supabase || !studentId || !programs?.length) return { error: null };

  const rows = programs.map((p) => ({
    student_id: studentId,
    config_id: p.config_id,
    display_name: p.display_name,
    program_type: p.program_type || "major",
  }));

  const { error } = await supabase.from("student_programs").upsert(rows, {
    onConflict: "student_id,config_id",
  });
  return { error };
}

/** If signup stored majors before session was ready, flush once a session exists. */
export async function flushPendingPrograms(studentId) {
  const pending = readPendingPrograms();
  if (!pending?.length || !studentId) return;
  const { error } = await saveStudentPrograms(studentId, pending);
  if (!error) clearPendingPrograms();
  return { error };
}

/**
 * Replace declared programs (upsert new, delete removed).
 * @param {string} studentId
 * @param {ProgramRow[]} programs
 */
export async function replaceStudentPrograms(studentId, programs) {
  if (!supabase || !studentId) {
    return { error: new Error("Not signed in") };
  }
  const next = programs || [];
  const nextIds = next.map((p) => p.config_id);

  const { data: existing, error: loadErr } = await fetchStudentPrograms(studentId);
  if (loadErr) return { error: loadErr };

  const keep = new Set(nextIds);
  const removed = (existing || [])
    .map((p) => p.config_id)
    .filter((id) => !keep.has(id));

  if (removed.length) {
    const { error: delErr } = await supabase
      .from("student_programs")
      .delete()
      .eq("student_id", studentId)
      .in("config_id", removed);
    if (delErr) return { error: delErr };

    await supabase
      .from("student_group_overrides")
      .delete()
      .eq("student_id", studentId)
      .in("config_id", removed);
  }

  if (next.length) {
    return saveStudentPrograms(studentId, next);
  }
  return { error: null };
}

/** Load declared programs for the signed-in user. */
export async function fetchStudentPrograms(studentId) {
  if (!supabase || !studentId) return { data: [], error: null };
  const { data, error } = await supabase
    .from("student_programs")
    .select("config_id, display_name, program_type")
    .eq("student_id", studentId)
    .order("display_name");
  return { data: data || [], error };
}
