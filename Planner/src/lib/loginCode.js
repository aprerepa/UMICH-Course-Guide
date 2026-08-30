const CHARS = "abcdefghijklmnopqrstuvwxyz0123456789";
const PREFIX = "umich-";
const SUFFIX_LENGTH = 12;
/** Synthetic inbox domain — must pass Supabase email validation (no .internal, etc.). */
const AUTH_EMAIL_DOMAIN = "example.com";

/** 12-char body without the umich- prefix. */
export function loginCodeSuffix(loginCode) {
  return normalizeLoginCode(loginCode).replace(/^umich-/, "");
}

/** @returns {string} e.g. umich-a3k9m2x7p1q4 */
export function generateLoginCode() {
  const bytes = new Uint8Array(SUFFIX_LENGTH);
  crypto.getRandomValues(bytes);
  let suffix = "";
  for (let i = 0; i < SUFFIX_LENGTH; i += 1) {
    suffix += CHARS[bytes[i] % CHARS.length];
  }
  return `${PREFIX}${suffix}`;
}

/** Normalize to `umich-` + suffix (allows typing with or without prefix). */
export function normalizeLoginCode(input) {
  let s = String(input || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9-]/g, "");
  if (s.startsWith("umich-")) {
    s = s.slice(6);
  } else if (s.startsWith("umich")) {
    s = s.slice(5).replace(/^-/, "");
  }
  s = s.replace(/-/g, "");
  if (!s) return "";
  return `${PREFIX}${s}`;
}

/** Display/storage form — same as normalized passkey. */
export function formatLoginCode(raw) {
  return normalizeLoginCode(raw);
}

/** Internal Supabase auth email — alphanumeric local part only (not the display code). */
export function loginCodeToAuthEmail(loginCode) {
  const suffix = loginCodeSuffix(loginCode);
  if (!suffix || suffix.length !== SUFFIX_LENGTH) {
    throw new Error("Enter your login code.");
  }
  return `${suffix}@${AUTH_EMAIL_DOMAIN}`;
}

export function isValidLoginCode(input) {
  return /^umich-[a-z0-9]{12}$/.test(normalizeLoginCode(input));
}

/** @param {string | null | undefined} authEmail */
export function loginCodeFromAuthEmail(authEmail) {
  const local = String(authEmail || "").split("@")[0] || "";
  if (!local) return "";
  if (/^[a-z0-9]{12}$/.test(local)) {
    return `umich-${local}`;
  }
  // Legacy accounts created before auth-email mapping fix
  if (local.startsWith("umich-") && isValidLoginCode(local)) {
    return normalizeLoginCode(local);
  }
  return "";
}
