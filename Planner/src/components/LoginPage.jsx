import { useMemo, useState } from "react";
import { useAuth } from "../context/AuthContext";
import {
  saveStudentPrograms,
  stashPendingPrograms,
} from "../lib/studentPrograms";
import { stashPendingLoginCode } from "./LoginCodeReveal";
import { MajorPicker, programsFromIds } from "./MajorPicker";

const styles = {
  page: {
    fontFamily: "'Georgia', 'Times New Roman', serif",
    backgroundColor: "#f5f5f3",
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px",
    boxSizing: "border-box",
  },
  card: {
    width: "min(480px, 100%)",
    background: "#fff",
    border: "1px solid #e4e4e4",
    borderRadius: "12px",
    padding: "32px 28px",
    boxShadow: "0 4px 24px rgba(0,0,0,0.04)",
  },
  brand: {
    margin: "0 0 6px 0",
    fontSize: "26px",
    fontWeight: 700,
    color: "#1a1a1a",
    textAlign: "center",
  },
  subtitle: {
    margin: "0 0 24px 0",
    fontSize: "14px",
    color: "#888",
    textAlign: "center",
    fontFamily: "system-ui, sans-serif",
    lineHeight: 1.45,
  },
  label: {
    display: "block",
    fontSize: "12px",
    color: "#666",
    marginBottom: "4px",
    fontFamily: "system-ui, sans-serif",
  },
  input: {
    width: "100%",
    boxSizing: "border-box",
    border: "1px solid #ddd",
    borderRadius: "6px",
    padding: "10px 12px",
    fontSize: "14px",
    marginBottom: "14px",
    fontFamily: "system-ui, sans-serif",
  },
  codeInput: {
    width: "100%",
    boxSizing: "border-box",
    border: "1px solid #ddd",
    borderRadius: "6px",
    padding: "10px 12px",
    fontSize: "16px",
    marginBottom: "14px",
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    letterSpacing: "0.05em",
  },
  primary: {
    width: "100%",
    border: "1px solid #1a1a1a",
    background: "#1a1a1a",
    color: "#fff",
    borderRadius: "6px",
    padding: "10px 12px",
    cursor: "pointer",
    fontSize: "14px",
    fontFamily: "system-ui, sans-serif",
    marginTop: "4px",
  },
  ghost: {
    width: "100%",
    border: "1px solid #ccc",
    background: "#fff",
    color: "#222",
    borderRadius: "6px",
    padding: "10px 12px",
    cursor: "pointer",
    fontSize: "14px",
    fontFamily: "system-ui, sans-serif",
    marginTop: "10px",
  },
  error: {
    color: "#b00020",
    fontSize: "13px",
    marginBottom: "10px",
    fontFamily: "system-ui, sans-serif",
  },
  info: {
    color: "#2a7a3a",
    fontSize: "13px",
    marginBottom: "10px",
    fontFamily: "system-ui, sans-serif",
  },
  switch: {
    marginTop: "18px",
    fontSize: "13px",
    color: "#666",
    textAlign: "center",
    fontFamily: "system-ui, sans-serif",
  },
  link: {
    background: "none",
    border: "none",
    color: "#2a52be",
    cursor: "pointer",
    padding: 0,
    fontSize: "13px",
    fontFamily: "system-ui, sans-serif",
  },
  divider: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    margin: "18px 0 8px",
    color: "#aaa",
    fontSize: "12px",
    fontFamily: "system-ui, sans-serif",
  },
  line: {
    flex: 1,
    height: 1,
    background: "#e8e8e8",
  },
  muted: {
    textAlign: "center",
    fontSize: "13px",
    color: "#888",
    fontFamily: "system-ui, sans-serif",
  },
  hint: {
    fontSize: "11px",
    color: "#999",
    margin: "-8px 0 12px",
    fontFamily: "system-ui, sans-serif",
    lineHeight: 1.45,
  },
  privacy: {
    fontSize: "12px",
    color: "#777",
    margin: "0 0 16px",
    fontFamily: "system-ui, sans-serif",
    lineHeight: 1.45,
    textAlign: "center",
  },
};

export function LoginPage() {
  const { configured, authError, signIn, signUp, continueAsGuest, reloadPrograms } =
    useAuth();
  const [mode, setMode] = useState("signin");
  const [loginCode, setLoginCode] = useState("");
  const [password, setPassword] = useState("");
  const [selectedIds, setSelectedIds] = useState([]);
  const [busy, setBusy] = useState(false);
  const [localError, setLocalError] = useState(null);
  const [info, setInfo] = useState(null);

  const selectedMajors = useMemo(
    () => programsFromIds(selectedIds),
    [selectedIds]
  );

  function toggleMajor(id) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  function programsPayload() {
    return selectedMajors;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (!configured) return;
    setBusy(true);
    setLocalError(null);
    setInfo(null);
    try {
      if (mode === "signin") {
        await signIn(loginCode, password);
      } else {
        if (selectedIds.length === 0) {
          setLocalError("Select at least one major (or sub-major).");
          setBusy(false);
          return;
        }
        const programs = programsPayload();
        const data = await signUp(password);
        stashPendingLoginCode(data.loginCode);
        if (data.session?.user) {
          const { error } = await saveStudentPrograms(
            data.session.user.id,
            programs
          );
          if (error) {
            stashPendingPrograms(programs);
            setLocalError(
              `Account created, but saving majors failed: ${error.message}`
            );
          } else if (reloadPrograms) {
            await reloadPrograms();
          }
        } else {
          stashPendingPrograms(programs);
          setInfo(
            "Account created. Sign in with your login code and password."
          );
        }
      }
    } catch (err) {
      setLocalError(err.message || "Auth failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={styles.brand}>UMich Course Guide</h1>
        <p style={styles.subtitle}>
          Sign in with your login code to personalize your guide, or continue as
          a guest to browse all majors.
        </p>

        {!configured ? (
          <p style={styles.muted}>
            Sign-in isn’t configured. You can still open the general course guide.
          </p>
        ) : (
          <form onSubmit={handleSubmit}>
            {mode === "signin" ? (
              <>
                <label style={styles.label} htmlFor="login-code">
                  Login code
                </label>
                <input
                  id="login-code"
                  style={styles.codeInput}
                  type="text"
                  autoComplete="username"
                  placeholder="umich-xxxxxxxxxxxx"
                  value={loginCode}
                  onChange={(e) => setLoginCode(e.target.value.toLowerCase())}
                  required
                />
              </>
            ) : (
              <p style={styles.privacy}>
                No student email required. We&apos;ll generate a private login
                code when you create your account.
              </p>
            )}
            <label style={styles.label} htmlFor="login-password">
              Password
            </label>
            <input
              id="login-password"
              style={styles.input}
              type="password"
              autoComplete={
                mode === "signin" ? "current-password" : "new-password"
              }
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={6}
              required
            />

            {mode === "signup" && (
              <>
                <label style={styles.label}>Your majors</label>
                <p style={styles.hint}>
                  Select one or more programs (search to filter the list).
                </p>
                <div style={{ marginBottom: "14px" }}>
                  <MajorPicker selectedIds={selectedIds} onToggle={toggleMajor} />
                </div>
              </>
            )}

            {(localError || authError) && (
              <div style={styles.error}>{localError || authError}</div>
            )}
            {info && <div style={styles.info}>{info}</div>}
            <button type="submit" style={styles.primary} disabled={busy}>
              {busy
                ? "Please wait…"
                : mode === "signin"
                  ? "Sign in"
                  : "Create account"}
            </button>
            <div style={styles.switch}>
              {mode === "signin" ? (
                <>
                  Need an account?{" "}
                  <button
                    type="button"
                    style={styles.link}
                    onClick={() => {
                      setMode("signup");
                      setLocalError(null);
                      setInfo(null);
                    }}
                  >
                    Sign up
                  </button>
                </>
              ) : (
                <>
                  Already have an account?{" "}
                  <button
                    type="button"
                    style={styles.link}
                    onClick={() => {
                      setMode("signin");
                      setLocalError(null);
                      setInfo(null);
                    }}
                  >
                    Sign in
                  </button>
                </>
              )}
            </div>
          </form>
        )}

        <div style={styles.divider}>
          <div style={styles.line} />
          <span>or</span>
          <div style={styles.line} />
        </div>

        <button
          type="button"
          style={styles.ghost}
          onClick={continueAsGuest}
          disabled={busy}
        >
          Continue to general course guide
        </button>
      </div>
    </div>
  );
}
