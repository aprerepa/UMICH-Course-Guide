/** Full major configs for requirement eligibility (not SOC offerings). */

import { normalizeCourseCode } from "../lib/completion";

const modules = import.meta.glob("../../config/majors/*.json", { eager: true });

/** When courses.json names differ from config displayName / id. */
const DISPLAY_ALIASES = {
  "computer science (lsa)": "computer-science-lsa",
  "computer science (bs)": "computer-science-lsa",
  "data science (lsa)": "data-science-lsa",
  "data science (bs)": "data-science-lsa",
};

/** @type {Map<string, object>} */
const byId = new Map();
/** @type {Map<string, object>} */
const byDisplayName = new Map();

for (const mod of Object.values(modules)) {
  const d = mod.default ?? mod;
  if (!d?.id) continue;
  byId.set(d.id, d);
  if (d.displayName) {
    byDisplayName.set(String(d.displayName).toLowerCase(), d);
  }
}

export function getMajorConfig({ configId, displayName } = {}) {
  if (configId && byId.has(configId)) return byId.get(configId);

  const nameKey = displayName ? String(displayName).toLowerCase() : "";
  if (nameKey && byDisplayName.has(nameKey)) return byDisplayName.get(nameKey);

  if (nameKey && DISPLAY_ALIASES[nameKey] && byId.has(DISPLAY_ALIASES[nameKey])) {
    return byId.get(DISPLAY_ALIASES[nameKey]);
  }

  return null;
}

function parseCode(code) {
  const n = normalizeCourseCode(code);
  const m = n.match(/^([A-Z][A-Z0-9]+)\s+(\d{2,4}[A-Z]?)$/i);
  if (!m) return null;
  return { code: n, subject: m[1].toUpperCase(), catalog: m[2], level: Number(m[2].replace(/\D/g, "").slice(0, 3)) || 0 };
}

/** @param {object|object[]} openSpec */
function matchesOpenSpec(openSpec, parsed) {
  const rules = Array.isArray(openSpec) ? openSpec : [openSpec];
  for (const rule of rules) {
    if (!rule || typeof rule !== "object") continue;
    const subjects = (rule.subjects || []).map((s) => String(s).toUpperCase());
    if (subjects.length && !subjects.includes(parsed.subject)) continue;
    const minLevel = Number(rule.minLevel) || 0;
    if (minLevel && parsed.level < minLevel) continue;
    const maxLevel = Number(rule.maxLevel) || 0;
    if (maxLevel && parsed.level > maxLevel) continue;
    const exclude = new Set(
      (rule.exclude || []).map((c) => normalizeCourseCode(c)).filter(Boolean)
    );
    if (exclude.has(parsed.code)) continue;
    return true;
  }
  return false;
}

/**
 * Whether a taken course code can count toward a named requirement group,
 * based on the major config (explicit lists + openGroups) — not SOC term offerings.
 */
export function isCodeEligibleForGroup(config, groupName, courseCode) {
  if (!config || !groupName) return false;
  const parsed = parseCode(courseCode);
  if (!parsed) return false;

  const explicit = config.requirementGroups?.[groupName];
  if (Array.isArray(explicit)) {
    for (const c of explicit) {
      if (normalizeCourseCode(c) === parsed.code) return true;
    }
  }

  const open = config.openGroups?.[groupName];
  if (open && matchesOpenSpec(open, parsed)) return true;

  // Case-insensitive group key fallback
  const lower = groupName.toLowerCase();
  for (const [key, list] of Object.entries(config.requirementGroups || {})) {
    if (key.toLowerCase() !== lower || !Array.isArray(list)) continue;
    for (const c of list) {
      if (normalizeCourseCode(c) === parsed.code) return true;
    }
  }
  for (const [key, spec] of Object.entries(config.openGroups || {})) {
    if (key.toLowerCase() !== lower) continue;
    if (matchesOpenSpec(spec, parsed)) return true;
  }

  return false;
}

/** Taken codes that count for this group (config-based eligibility). */
export function groupHitCodesFromConfig(config, groupName, takenSet) {
  if (!config || !takenSet?.size) return [];
  const hits = [];
  for (const code of takenSet) {
    if (isCodeEligibleForGroup(config, groupName, code)) hits.push(code);
  }
  return hits;
}
