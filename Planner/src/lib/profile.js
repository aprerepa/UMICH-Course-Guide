import { supabase } from "./supabase";

/** @param {string} userId */
export async function fetchLoginCode(userId) {
  if (!supabase || !userId) return { loginCode: null, error: null };
  const { data, error } = await supabase
    .from("profiles")
    .select("login_code")
    .eq("id", userId)
    .maybeSingle();
  if (error) return { loginCode: null, error };
  return { loginCode: data?.login_code ?? null, error: null };
}
