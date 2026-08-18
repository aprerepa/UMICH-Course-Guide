import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

/**
 * Implicit flow so email-confirmation links work on a different device
 * than the one used to sign up (PKCE needs a stored code verifier).
 */
export const supabase =
  url && anonKey
    ? createClient(url, anonKey, {
        auth: {
          flowType: "implicit",
          detectSessionInUrl: true,
        },
      })
    : null;

export function isSupabaseConfigured() {
  return Boolean(supabase);
}
