/** Rules catalog keyed by config id and displayName. */

import { MAJOR_OPTIONS } from "./majorCatalog";

const modules = import.meta.glob("../../config/rules/*.json", { eager: true });

/** When courses.json / major config names differ from rules extract ids. */
const DISPLAY_ALIASES = {
  "computer science (lsa)":
    "computer-science-bs--majors-minors-html-computer-science-maj",
  "computer science (bs)":
    "computer-science-bs--majors-minors-html-computer-science-maj",
  "data science (lsa)":
    "data-science-bs--majors-minors-html-data-science-maj",
  "data science (bs)":
    "data-science-bs--majors-minors-html-data-science-maj",
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

/** Look up rules by major config id or courses.json display name. */
export function getRulesForMajor({ configId, displayName } = {}) {
  if (configId && byId.has(configId)) return byId.get(configId);

  const nameKey = displayName ? String(displayName).toLowerCase() : "";
  if (nameKey && byDisplayName.has(nameKey)) return byDisplayName.get(nameKey);

  if (nameKey && DISPLAY_ALIASES[nameKey]) {
    const aliased = byId.get(DISPLAY_ALIASES[nameKey]);
    if (aliased) return aliased;
  }

  if (displayName) {
    const majorOpt = MAJOR_OPTIONS.find(
      (m) => m.displayName.toLowerCase() === nameKey
    );
    if (majorOpt && byId.has(majorOpt.id)) return byId.get(majorOpt.id);
  }

  return null;
}

export function getGroupRules(rulesDoc) {
  return rulesDoc?.groupRules && typeof rulesDoc.groupRules === "object"
    ? rulesDoc.groupRules
    : {};
}
