import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

/** Session ends when the browser tab closes (not persisted across visits). */
const authStorage =
  typeof window !== "undefined" ? window.sessionStorage : undefined;

/** Shared Supabase client, or null if env vars are missing (guest mode). */
export const supabase =
  url && anonKey
    ? createClient(url, anonKey, {
        auth: {
          storage: authStorage,
          persistSession: true,
          autoRefreshToken: true,
        },
      })
    : null;

export function isSupabaseConfigured() {
  return Boolean(supabase);
}
