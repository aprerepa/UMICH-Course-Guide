import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { supabase, isSupabaseConfigured } from "../lib/supabase";
import {
  fetchStudentPrograms,
  flushPendingPrograms,
} from "../lib/studentPrograms";

const GUEST_KEY = "courseGuideGuest";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession] = useState(null);
  const [loading, setLoading] = useState(isSupabaseConfigured());
  const [authError, setAuthError] = useState(null);
  const [programs, setPrograms] = useState([]);
  const [programsLoading, setProgramsLoading] = useState(false);
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
    const inApp = Boolean(user) || guest;

    async function signUp(email, password) {
      setAuthError(null);
      if (!supabase) throw new Error("Supabase is not configured");
      const { data, error } = await supabase.auth.signUp({ email, password });
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
  }, [session, loading, authError, guest, programs, programsLoading]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
