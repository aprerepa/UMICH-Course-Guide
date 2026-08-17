import { supabase } from "./supabase";

const TABLES = [
  "student_completed_courses",
  "student_group_overrides",
  "student_programs",
  "transcript_uploads",
];

/**
 * Wipe all public rows for this user, then remove the auth user via RPC.
 * Requires course_guide_delete_account.sql (delete_own_account + profile DELETE policy).
 * @param {string} studentId
 */
export async function deleteOwnAccount(studentId) {
  if (!supabase || !studentId) {
    return { error: new Error("Not signed in") };
  }

  for (const table of TABLES) {
    const { error } = await supabase
      .from(table)
      .delete()
      .eq("student_id", studentId);
    if (error) return { error };
  }

  await supabase.from("profiles").delete().eq("id", studentId);

  const { error: rpcErr } = await supabase.rpc("delete_own_account");
  if (rpcErr) {
    return {
      error: new Error(
        `${rpcErr.message} Run course_guide_delete_account.sql in the Supabase SQL editor so the login can be removed too.`
      ),
    };
  }

  return { error: null };
}
