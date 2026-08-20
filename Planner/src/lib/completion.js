/**
 * Group completion helpers for config/rules groupRules.
 *
 * Clause shapes (under rule.require):
 *   "SUBJ 123"                         — that course taken
 *   { anyOf: Clause[] }                — at least one
 *   { allOf: Clause[] }                — all
 *   { minOf: n, options: Clause[] }    — at least n options satisfied
 *   { minCredits: n, from: string[] }  — at least n credits among those codes
 *
 * Quota fields (alongside or instead of require):
 *   minCourses, minCredits, completion: "manual"
 */

/** @param {string} code */
export function normalizeCourseCode(code) {
  if (typeof code !== "string") return "";
  return code.trim().toUpperCase().replace(/\s+/g, " ");
}

/** @param {Iterable<string>} codes */
export function toTakenSet(codes) {
  const set = new Set();
  for (const c of codes || []) {
    const n = normalizeCourseCode(c);
    if (n) set.add(n);
  }
  return set;
}

/**
 * @param {unknown} clause
 * @param {Set<string>} taken
 * @param {Record<string, number>} [creditByCode]
 * @returns {boolean}
 */
export function isClauseSatisfied(clause, taken, creditByCode = {}) {
  if (typeof clause === "string") {
    const code = normalizeCourseCode(clause);
    return Boolean(code && taken.has(code));
  }
  if (!clause || typeof clause !== "object" || Array.isArray(clause)) {
    return false;
  }

  if (Array.isArray(clause.anyOf)) {
    return clause.anyOf.some((c) => isClauseSatisfied(c, taken, creditByCode));
  }
  if (Array.isArray(clause.allOf)) {
    return (
      clause.allOf.length > 0 &&
      clause.allOf.every((c) => isClauseSatisfied(c, taken, creditByCode))
    );
  }
  if (
    typeof clause.minOf === "number" &&
    clause.minOf > 0 &&
    Array.isArray(clause.options)
  ) {
    let n = 0;
    for (const opt of clause.options) {
      if (isClauseSatisfied(opt, taken, creditByCode)) n += 1;
      if (n >= clause.minOf) return true;
    }
    return false;
  }
  if (typeof clause.minCredits === "number" && clause.minCredits > 0) {
    const from = Array.isArray(clause.from) ? clause.from : [];
    let credits = 0;
    const seen = new Set();
    for (const raw of from) {
      const code = normalizeCourseCode(raw);
      if (!code || seen.has(code) || !taken.has(code)) continue;
      seen.add(code);
      const c = creditByCode[code];
      credits += typeof c === "number" && c > 0 ? c : 3;
    }
    return credits >= clause.minCredits;
  }

  return false;
}

/**
 * @param {{ minCourses?: number, minCredits?: number }} rule
 * @param {string[]} hitCodes — taken codes that count for this group
 * @param {Record<string, number>} [creditByCode]
 */
export function isQuotaMet(rule, hitCodes, creditByCode = {}) {
  const hits = (hitCodes || []).map(normalizeCourseCode).filter(Boolean);
  const unique = [...new Set(hits)];

  if (typeof rule.minCourses === "number" && rule.minCourses > 0) {
    if (unique.length < rule.minCourses) return false;
  }

  if (typeof rule.minCredits === "number" && rule.minCredits > 0) {
    let credits = 0;
    for (const code of unique) {
      const c = creditByCode[code];
      if (typeof c === "number" && c > 0) credits += c;
    }
    if (credits < rule.minCredits) return false;
  }

  // If only quotas were requested and neither field present, not met
  const hasQuota =
    (typeof rule.minCourses === "number" && rule.minCourses > 0) ||
    (typeof rule.minCredits === "number" && rule.minCredits > 0);
  return hasQuota;
}

/**
 * @param {object | undefined} rule — groupRules[groupName]
 * @param {object} opts
 * @param {Iterable<string>} opts.takenCodes
 * @param {string[]} [opts.groupHitCodes] — taken ∩ group eligible (for quotas)
 * @param {Record<string, number>} [opts.creditByCode]
 * @param {boolean} [opts.manualOverride] — student marked complete
 * @returns {{ complete: boolean, reason: string }}
 */
export function isGroupComplete(rule, opts = {}) {
  const taken = toTakenSet(opts.takenCodes || []);
  const manualOverride = Boolean(opts.manualOverride);

  if (!rule || typeof rule !== "object") {
    return { complete: false, reason: "no-rule" };
  }

  if (manualOverride) {
    return { complete: true, reason: "override" };
  }

  if (rule.require != null) {
    const ok = isClauseSatisfied(rule.require, taken, opts.creditByCode || {});
    return { complete: ok, reason: ok ? "require" : "require-unmet" };
  }

  if (rule.completion === "manual") {
    return { complete: false, reason: "manual" };
  }

  const ok = isQuotaMet(rule, opts.groupHitCodes || [], opts.creditByCode || {});
  return { complete: ok, reason: ok ? "quota" : "quota-unmet" };
}
