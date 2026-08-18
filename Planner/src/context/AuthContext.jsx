import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { supabase, isSupabaseConfigured } from "../lib/supabase";
import {
  fetchStudentPrograms,
  flushPendingPrograms,
} from "../lib/studentPrograms";

const GUEST_KEY = "courseGuideGuest";

/** True when returning from the Supabase email-confirmation link. */
function detectEmailConfirmRedirect() {
  try {
    const params = new URLSearchParams(window.location.search);
    if (params.get("auth") === "confirmed") return true;
    const hash = window.location.hash.replace(/^#/, "");
    if (!hash) return false;
    const hashParams = new URLSearchParams(hash);
    const type = hashParams.get("type");
    return type === "signup" || type === "email" || type === "email_change";
  } catch {
    return false;
  }
}

function authRedirectUrl() {
  const path = window.location.pathname || "/";
  return `${window.location.origin}${path}?auth=confirmed`;
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(isSupabaseConfigured());
  const [authError, setAuthError] = useState(null);
  const [programs, setPrograms] = useState([]);
  const [programsLoading, setProgramsLoading] = useState(false);
  const [postConfirm, setPostConfirm] = useState(detectEmailConfirmRedirect);
  const [guest, setGuest] = useState(() => {
    try {
      return sessionStorage.getItem(GUEST_KEY) === "1";
    } catch {
      return false;
    }
  });

  async function reloadPrograms(userId) {
    if (!userId) {
      setPrograms([]);
      return;
    }
    setProgramsLoading(true);
    const { data, error } = await fetchStudentPrograms(userId);
    if (!error) setPrograms(data);
    setProgramsLoading(false);
  }

  useEffect(() => {
    if (!postConfirm) return;
    try {
      const url = new URL(window.location.href);
      url.searchParams.delete("auth");
      url.hash = "";
      window.history.replaceState({}, "", url.pathname + url.search);
    } catch {
      /* ignore */
    }
  }, [postConfirm]);

  useEffect(() => {
    if (!supabase) {
      setGuest(true);
      setLoading(false);
      return;
    }

    let mounted = true;

    async function onSession(next) {
      setSession(next);
      if (next?.user) {
        try {
          sessionStorage.removeItem(GUEST_KEY);
        } catch {
          /* ignore */
        }
        setGuest(false);
        await flushPendingPrograms(next.user.id);
        if (mounted) await reloadPrograms(next.user.id);
      } else if (mounted) {
        setPrograms([]);
      }
    }

    supabase.auth.getSession().then(async ({ data, error }) => {
      if (!mounted) return;
      if (error) setAuthError(error.message);
      await onSession(data.session ?? null);
      if (mounted) setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setAuthError(null);
      onSession(next);
    });

    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  const value = useMemo(() => {
    const user = session?.user ?? null;
    // After email confirm, stay on login until the user signs in explicitly.
    const inApp = (Boolean(user) && !postConfirm) || guest;

    async function signUp(email, password) {
      setAuthError(null);
      if (!supabase) throw new Error("Supabase is not configured");
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
        options: { emailRedirectTo: authRedirectUrl() },
      });
      if (error) {
        setAuthError(error.message);
        throw error;
      }
      return data;
    }

    async function signIn(email, password) {
      setAuthError(null);
      if (!supabase) throw new Error("Supabase is not configured");
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) {
        setAuthError(error.message);
        throw error;
      }
      setPostConfirm(false);
      return data;
    }

    function clearPostConfirm() {
      setPostConfirm(false);
    }

    async function signOut() {
      setAuthError(null);
      try {
        sessionStorage.removeItem(GUEST_KEY);
      } catch {
        /* ignore */
      }
      setGuest(false);
      setPrograms([]);
      if (!supabase) return;
      const { error } = await supabase.auth.signOut();
      if (error) {
        setAuthError(error.message);
        throw error;
      }
    }

    function continueAsGuest() {
      try {
        sessionStorage.setItem(GUEST_KEY, "1");
      } catch {
        /* ignore */
      }
      setGuest(true);
      setPrograms([]);
    }

    function returnToLogin() {
      try {
        sessionStorage.removeItem(GUEST_KEY);
      } catch {
        /* ignore */
      }
      setGuest(false);
    }

    return {
      configured: isSupabaseConfigured(),
      loading,
      session,
      user,
      guest,
      inApp,
      postConfirm,
      authError,
      programs,
      programsLoading,
      reloadPrograms: () => reloadPrograms(user?.id),
      signUp,
      signIn,
      signOut,
      continueAsGuest,
      returnToLogin,
      clearPostConfirm,
    };
  }, [session, loading, authError, guest, postConfirm, programs, programsLoading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
