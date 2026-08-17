import { useEffect, useRef, useState } from "react";
import { useAuth } from "../context/AuthContext";
import { emailInitials } from "./Icons";

const styles = {
  bar: {
    display: "flex",
    justifyContent: "flex-end",
    alignItems: "center",
    gap: "10px",
    marginBottom: "16px",
    fontFamily: "system-ui, sans-serif",
    fontSize: "13px",
  },
  muted: {
    color: "#888",
  },
  button: {
    border: "1px solid #ccc",
    background: "#fff",
    borderRadius: "6px",
    padding: "6px 12px",
    cursor: "pointer",
    fontSize: "13px",
    color: "#222",
  },
  wrap: {
    position: "relative",
  },
  avatar: (open) => ({
    width: 36,
    height: 36,
    borderRadius: "50%",
    border: open ? "2px solid #4a7cf6" : "2px solid #fff",
    boxShadow: open ? "0 0 0 1px #4a7cf6" : "0 0 0 1px #d4d4d4",
    background: "#4a7cf6",
    color: "#fff",
    fontSize: "12px",
    fontWeight: 700,
    letterSpacing: "0.02em",
    cursor: "pointer",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 0,
    fontFamily: "system-ui, sans-serif",
  }),
  menu: {
    position: "absolute",
    top: "calc(100% + 8px)",
    right: 0,
    width: 240,
    background: "#fff",
    border: "1px solid #e4e4e4",
    borderRadius: "10px",
    boxShadow: "0 8px 24px rgba(0,0,0,0.12)",
    zIndex: 200,
    overflow: "hidden",
  },
  identity: {
    padding: "12px 14px",
    borderBottom: "1px solid #f0f0f0",
  },
  identityLabel: {
    fontSize: "11px",
    fontWeight: 600,
    color: "#888",
    marginBottom: "2px",
  },
  identityEmail: {
    fontSize: "13px",
    color: "#222",
    wordBreak: "break-all",
  },
  item: {
    display: "block",
    width: "100%",
    textAlign: "left",
    border: "none",
    background: "transparent",
    padding: "10px 14px",
    fontSize: "13.5px",
    color: "#222",
    cursor: "pointer",
    fontFamily: "system-ui, sans-serif",
  },
  itemDanger: {
    color: "#b00020",
    borderTop: "1px solid #f0f0f0",
  },
};

/**
 * @param {"guide" | "settings"} page
 * @param {(next: "guide" | "settings") => void} onNavigate
 */
export function GuideHeader({ page = "guide", onNavigate }) {
  const { user, guest, signOut, returnToLogin } = useAuth();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    function onDoc(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    function onKey(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    setOpen(false);
  }, [page]);

  return (
    <div style={styles.bar}>
      {user ? (
        <div style={styles.wrap} ref={wrapRef}>
          <button
            type="button"
            style={styles.avatar(open)}
            aria-label="Account menu"
            aria-expanded={open}
            onClick={() => setOpen((v) => !v)}
          >
            {emailInitials(user.email)}
          </button>
          {open && (
            <div style={styles.menu} role="menu">
              <div style={styles.identity}>
                <div style={styles.identityLabel}>Signed in as</div>
                <div style={styles.identityEmail}>{user.email}</div>
              </div>
              <button
                type="button"
                role="menuitem"
                style={styles.item}
                onClick={() => {
                  setOpen(false);
                  onNavigate?.("settings");
                }}
              >
                Settings
              </button>
              {page === "settings" && (
                <button
                  type="button"
                  role="menuitem"
                  style={styles.item}
                  onClick={() => {
                    setOpen(false);
                    onNavigate?.("guide");
                  }}
                >
                  Course guide
                </button>
              )}
              <button
                type="button"
                role="menuitem"
                style={{ ...styles.item, ...styles.itemDanger }}
                onClick={() => {
                  setOpen(false);
                  signOut();
                }}
              >
                Sign out
              </button>
            </div>
          )}
        </div>
      ) : guest ? (
        <>
          <span style={styles.muted}>Browsing as guest</span>
          <button type="button" style={styles.button} onClick={returnToLogin}>
            Sign in
          </button>
        </>
      ) : null}
    </div>
  );
}
