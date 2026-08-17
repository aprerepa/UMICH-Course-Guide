/** Catalog of extractable majors for signup / profile (id matches config JSON). */

const modules = import.meta.glob("../../config/majors/*.json", { eager: true });

/**
 * Infer major vs minor vs sub-major from the human display name only.
 * Do NOT use config ids — LSA slugs contain "majors-minors" and false-trigger "minor".
 */
function inferProgramType(displayName) {
  const name = (displayName || "").toLowerCase();
  if (/\bsub-?\s*major\b/.test(name)) return "submajor";
  // e.g. "Medical Anthropology (Minor)" — not LSA URL fragments like majors-minors
  if (/\(\s*minor\s*\)|\bminor\b/.test(name) && !/\bmajor\b/.test(name)) {
    return "minor";
  }
  return "major";
}

export const MAJOR_OPTIONS = Object.values(modules)
  .map((mod) => {
    const d = mod.default ?? mod;
    const displayName = d.displayName || d.id;
    return {
      id: d.id,
      displayName,
      programType: inferProgramType(displayName),
    };
  })
  .filter((m) => m.id && m.displayName)
  .sort((a, b) =>
    a.displayName.localeCompare(b.displayName, undefined, { sensitivity: "base" })
  );

export function getMajorOption(configId) {
  return MAJOR_OPTIONS.find((m) => m.id === configId) || null;
}
