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
 *
 * Overlap:
 *   By default, a taken course is allocated to at most one exclusive quota
 *   group (so Group A courses cannot also satisfy Group D electives).
 *   Set mayOverlap: true when a group may share courses with others
 *   (e.g. BHS Lab, WGS thematic areas that allow one double-count).
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
      else credits += 3;
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
 * @param {{ minCourses?: number, minCredits?: number }} rule
 */
function hasQuotaFields(rule) {
  return (
    (typeof rule?.minCourses === "number" && rule.minCourses > 0) ||
    (typeof rule?.minCredits === "number" && rule.minCredits > 0)
  );
}

/**
 * Greedily pick the fewest leading courses that satisfy minCourses/minCredits.
 * @param {string[]} eligibleSorted
 * @param {{ minCourses?: number, minCredits?: number }} rule
 * @param {Record<string, number>} creditByCode
 * @returns {string[]}
 */
export function pickCodesForQuota(eligibleSorted, rule, creditByCode = {}) {
  const needCourses =
    typeof rule.minCourses === "number" && rule.minCourses > 0
      ? rule.minCourses
      : 0;
  const needCredits =
    typeof rule.minCredits === "number" && rule.minCredits > 0
      ? rule.minCredits
      : 0;
  if (!needCourses && !needCredits) return [];

  const picked = [];
  let credits = 0;
  for (const code of eligibleSorted) {
    const coursesOk = !needCourses || picked.length >= needCourses;
    const creditsOk = !needCredits || credits >= needCredits;
    if (coursesOk && creditsOk) break;
    picked.push(code);
    const c = creditByCode[code];
    credits += typeof c === "number" && c > 0 ? c : 3;
  }
  return picked;
}

/**
 * Whether picked codes already meet the group's course/credit quotas.
 * @param {string[]} picked
 * @param {{ minCourses?: number, minCredits?: number }} rule
 * @param {Record<string, number>} creditByCode
 */
function quotaSatisfied(picked, rule, creditByCode) {
  return isQuotaMet(rule, picked, creditByCode);
}

/**
 * Allocate taken courses across groups so exclusive quota groups do not share.
 *
 * Strategy for exclusive groups:
 * 1. Prefer courses eligible for only one exclusive group (unique-first).
 * 2. Fill remaining quotas from shared leftovers in `groupNames` order.
 * Overlapping groups (`mayOverlap: true`) see all eligible taken codes and
 * do not consume the exclusive pool.
 *
 * @param {object} opts
 * @param {string[]} opts.groupNames — display order (config requirementGroups keys)
 * @param {Record<string, object>} opts.groupRules
 * @param {(groupName: string) => string[]} opts.getEligible — taken ∩ eligible for group
 * @param {Record<string, number>} [opts.creditByCode]
 * @returns {Map<string, string[]>} groupName → codes counted for that group
 */
export function allocateGroupHits({
  groupNames = [],
  groupRules = {},
  getEligible,
  creditByCode = {},
}) {
  /** @type {Map<string, string[]>} */
  const assigned = new Map();
  /** @type {Set<string>} */
  const remaining = new Set();

  const resolveRule = (name) => {
    if (groupRules[name]) return { name, rule: groupRules[name] };
    const lower = name.toLowerCase();
    for (const [key, rule] of Object.entries(groupRules)) {
      if (key.toLowerCase() === lower) return { name: key, rule };
    }
    return null;
  };

  /** @type {{ groupName: string, rule: object, eligible: string[] }[]} */
  const exclusive = [];
  /** @type {{ groupName: string, rule: object, eligible: string[] }[]} */
  const overlapping = [];

  for (const groupName of groupNames) {
    if (groupName === "All") continue;
    const resolved = resolveRule(groupName);
    if (!resolved) continue;
    const { rule } = resolved;
    if (rule.require != null || rule.completion === "manual") continue;
    if (!hasQuotaFields(rule)) continue;
    const eligible = (getEligible(groupName) || [])
      .map(normalizeCourseCode)
      .filter(Boolean);
    const uniqueEligible = [...new Set(eligible)].sort();
    for (const c of uniqueEligible) remaining.add(c);
    const entry = { groupName, rule, eligible: uniqueEligible };
    if (rule.mayOverlap === true) overlapping.push(entry);
    else exclusive.push(entry);
  }

  /** @type {Map<string, string[]>} */
  const picks = new Map();
  for (const { groupName } of exclusive) picks.set(groupName, []);

  const claim = (groupName, code) => {
    const list = picks.get(groupName);
    if (!list || list.includes(code) || !remaining.has(code)) return false;
    list.push(code);
    remaining.delete(code);
    return true;
  };

  // Pass 1: courses eligible for exactly one exclusive group
  for (const { groupName, rule, eligible } of exclusive) {
    if (quotaSatisfied(picks.get(groupName), rule, creditByCode)) continue;
    const unique = eligible.filter((code) => {
      if (!remaining.has(code)) return false;
      let owners = 0;
      for (const other of exclusive) {
        if (other.eligible.includes(code)) owners += 1;
      }
      return owners === 1;
    });
    for (const code of unique) {
      if (quotaSatisfied(picks.get(groupName), rule, creditByCode)) break;
      claim(groupName, code);
    }
  }

  // Pass 2: shared leftovers in config order (specific groups listed first)
  for (const { groupName, rule, eligible } of exclusive) {
    if (quotaSatisfied(picks.get(groupName), rule, creditByCode)) continue;
    const available = eligible.filter((c) => remaining.has(c)).sort();
    for (const code of available) {
      if (quotaSatisfied(picks.get(groupName), rule, creditByCode)) break;
      claim(groupName, code);
    }
  }

  for (const { groupName } of exclusive) {
    assigned.set(groupName, picks.get(groupName) || []);
  }

  for (const { groupName, eligible } of overlapping) {
    // May use any eligible taken course, including those assigned elsewhere
    assigned.set(groupName, [...eligible]);
  }

  return assigned;
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
