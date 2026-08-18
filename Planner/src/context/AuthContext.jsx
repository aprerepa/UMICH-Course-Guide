import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { supabase, isSupabaseConfigured } from "../lib/supabase";
import {
  fetchStudentPrograms,
  flushPendingPrograms,
} from "../lib/studentPrograms";

const GUEST_KEY = "courseGuideGuest";

function readHashParams() {
  try {
    const hash = window.location.hash.replace(/^#/, "");
    return hash ? new URLSearchParams(hash) : new URLSearchParams();
  } catch {
    return new URLSearchParams();
  }
}

function readSearchParams() {
  try {
    return new URLSearchParams(window.location.search);
  } catch {
    return new URLSearchParams();
  }
}

/** True when returning from the Supabase email-confirmation link. */
function detectEmailConfirmRedirect() {
  const search = readSearchParams();
  const hash = readHashParams();
  const type = hash.get("type") || search.get("type");
  return (
    Boolean(search.get("code")) ||
    Boolean(hash.get("access_token")) ||
    type === "signup" ||
    type === "email" ||
    type === "email_change" ||
    Boolean(search.get("error") || hash.get("error"))
  );
}

function confirmErrorFromUrl() {
  const search = readSearchParams();
  const hash = readHashParams();
  return (
    search.get("error_description") ||
    hash.get("error_description") ||
    search.get("error") ||
    hash.get("error") ||
    null
  );
}

/** No query string — a `?` inside redirect_to breaks the verify URL in Mail/Safari. */
function authRedirectUrl() {
  return `${window.location.origin}/`;
}

function stripAuthParamsFromUrl() {
  try {
    const url = new URL(window.location.href);
    url.hash = "";
    url.searchParams.delete("code");
    url.searchParams.delete("error");
    url.searchParams.delete("error_description");
    url.searchParams.delete("error_code");
    url.searchParams.delete("type");
    window.history.replaceState({}, "", url.pathname + (url.search || ""));
  } catch {
    /* ignore */
  }
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(isSupabaseConfigured());
  const [authError, setAuthError] = useState(null);
  const [programs, setPrograms] = useState([]);
  const [programsLoading, setProgramsLoading] = useState(false);
  const [postConfirm, setPostConfirm] = useState(false);
  const [confirmedEmail, setConfirmedEmail] = useState("");
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
    if (!supabase) {
      setGuest(true);
      setLoading(false);
      return;
    }

    let mounted = true;
    const fromConfirm = detectEmailConfirmRedirect();
    const urlError = confirmErrorFromUrl();

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

      if (fromConfirm) {
        const next = data.session ?? null;
        if (urlError && !next) {
          setAuthError(decodeURIComponent(urlError.replace(/\+/g, " ")));
        }
        if (next?.user) {
          setConfirmedEmail(next.user.email || "");
          await onSession(next);
          await supabase.auth.signOut();
          if (!mounted) return;
          setSession(null);
          setPrograms([]);
          setGuest(false);
        }
        setPostConfirm(true);
        stripAuthParamsFromUrl();
        if (mounted) setLoading(false);
        return;
      }

      await onSession(data.session ?? null);
      if (mounted) setLoading(false);
    });

    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      if (fromConfirm) return;
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
    const inApp = Boolean(user) || guest;

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
      confirmedEmail,
      authError,
      programs,
      programsLoading,
      reloadPrograms: () => reloadPrograms(user?.id),
      signUp,
      signIn,
      signOut,
      continueAsGuest,
      returnToLogin,
    };
  }, [
    session,
    loading,
    authError,
    guest,
    postConfirm,
    confirmedEmail,
    programs,
    programsLoading,
  ]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
