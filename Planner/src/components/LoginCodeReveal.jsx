import { useState } from "react";
import { formatLoginCode } from "../lib/loginCode";

const PENDING_KEY = "courseGuidePendingLoginCode";

const styles = {
  overlay: {
    position: "fixed",
    inset: 0,
    background: "rgba(0,0,0,0.45)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "24px",
    zIndex: 1000,
    boxSizing: "border-box",
  },
  card: {
    width: "min(440px, 100%)",
    background: "#fff",
    borderRadius: "12px",
    padding: "28px 24px",
    boxShadow: "0 12px 40px rgba(0,0,0,0.18)",
    fontFamily: "system-ui, sans-serif",
  },
  title: {
    margin: "0 0 8px",
    fontSize: "20px",
    fontWeight: 700,
    color: "#1a1a1a",
  },
  body: {
    margin: "0 0 18px",
    fontSize: "14px",
    lineHeight: 1.5,
    color: "#555",
  },
  codeBox: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
    marginBottom: "16px",
  },
  code: {
    flex: 1,
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace",
    fontSize: "18px",
    letterSpacing: "0.06em",
    padding: "12px 14px",
    background: "#f5f5f3",
    border: "1px solid #e0e0e0",
    borderRadius: "8px",
    color: "#1a1a1a",
    wordBreak: "break-all",
  },
  copy: {
    border: "1px solid #ccc",
    background: "#fff",
    borderRadius: "8px",
    padding: "10px 12px",
    cursor: "pointer",
    fontSize: "13px",
  },
  primary: {
    width: "100%",
    border: "1px solid #1a1a1a",
    background: "#1a1a1a",
    color: "#fff",
    borderRadius: "8px",
    padding: "11px 12px",
    cursor: "pointer",
    fontSize: "14px",
  },
  warn: {
    margin: "0 0 16px",
    fontSize: "13px",
    color: "#8a5a00",
    lineHeight: 1.45,
  },
};

export function readPendingLoginCode() {
  try {
    return sessionStorage.getItem(PENDING_KEY);
  } catch {
    return null;
  }
}

export function clearPendingLoginCode() {
  try {
    sessionStorage.removeItem(PENDING_KEY);
  } catch {
    /* ignore */
  }
}

export function stashPendingLoginCode(code) {
  try {
    sessionStorage.setItem(PENDING_KEY, formatLoginCode(code));
  } catch {
    /* ignore */
  }
}

export function LoginCodeReveal() {
  const [code, setCode] = useState(() => readPendingLoginCode());
  const [copied, setCopied] = useState(false);

  if (!code) return null;

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div style={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="login-code-title">
      <div style={styles.card}>
        <h2 id="login-code-title" style={styles.title}>
          Save your login code
        </h2>
        <p style={styles.body}>
          This is your username. We don&apos;t collect student emails — use this code with your
          password to sign in again. We can&apos;t recover it if you lose it.
        </p>
        <p style={styles.warn}>
          Copy it somewhere safe now. You won&apos;t see it again after you continue.
        </p>
        <div style={styles.codeBox}>
          <div style={styles.code}>{code}</div>
          <button type="button" style={styles.copy} onClick={copyCode}>
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
        <button
          type="button"
          style={styles.primary}
          onClick={() => {
            clearPendingLoginCode();
            setCode(null);
          }}
        >
          I&apos;ve saved my login code
        </button>
      </div>
    </div>
  );
}
