import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  allocateGroupHits,
  isClauseSatisfied,
  isGroupComplete,
  toTakenSet,
} from "./completion.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const bhsRules = JSON.parse(
  readFileSync(
    join(
      __dirname,
      "../../config/rules/biology-health-and-society--majors-minors-html-general-biology-maj.json"
    ),
    "utf8"
  )
);
const bhsMajor = JSON.parse(
  readFileSync(
    join(
      __dirname,
      "../../config/majors/biology-health-and-society--majors-minors-html-general-biology-maj.json"
    ),
    "utf8"
  )
);

/** Minimal eligibility for BHS allocation tests (explicit lists + Group D open band). */
function bhsEligible(groupName, takenSet) {
  const hits = [];
  const explicit = bhsMajor.requirementGroups?.[groupName] || [];
  for (const code of takenSet) {
    if (explicit.includes(code)) hits.push(code);
  }
  if (groupName === "Group D - Biology Elective") {
    for (const code of takenSet) {
      const m = /^([A-Z]+)\s+(\d+)/.exec(code);
      if (!m) continue;
      const [, subj, num] = m;
      if (!["BIOLOGY", "EEB", "MCDB"].includes(subj)) continue;
      if (Number(num) < 200) continue;
      if (!hits.includes(code)) hits.push(code);
    }
  }
  return hits;
}

const prereq = bhsRules.groupRules.Prerequisites.require;

test("intro bio sequence A", () => {
  const taken = toTakenSet(["BIOLOGY 171", "BIOLOGY 172", "BIOLOGY 173"]);
  // full prereq still needs chem + 3 quant — just check anyOf sequences via nested
  const sequences = prereq.allOf[0];
  assert.equal(isClauseSatisfied(sequences, taken), true);
});

test("intro bio sequence B", () => {
  const taken = toTakenSet(["BIOLOGY 195", "BIOLOGY 196"]);
  assert.equal(isClauseSatisfied(prereq.allOf[0], taken), true);
});

test("intro bio incomplete", () => {
  const taken = toTakenSet(["BIOLOGY 171", "BIOLOGY 173"]); // missing 172/174
  assert.equal(isClauseSatisfied(prereq.allOf[0], taken), false);
});

test("full BHS prerequisites complete", () => {
  const taken = [
    "BIOLOGY 171",
    "BIOLOGY 174",
    "BIOLOGY 173",
    "CHEM 210",
    "CHEM 211",
    "MATH 115",
    "MATH 116",
    "STATS 250",
  ];
  const r = isGroupComplete(bhsRules.groupRules.Prerequisites, {
    takenCodes: taken,
  });
  assert.equal(r.complete, true);
  assert.equal(r.reason, "require");
});

test("BHS prerequisites missing chem", () => {
  const taken = [
    "BIOLOGY 171",
    "BIOLOGY 172",
    "BIOLOGY 173",
    "MATH 115",
    "MATH 116",
    "STATS 250",
  ];
  const r = isGroupComplete(bhsRules.groupRules.Prerequisites, {
    takenCodes: taken,
  });
  assert.equal(r.complete, false);
});

test("Group A quota", () => {
  const r = isGroupComplete(bhsRules.groupRules["Group A: Gateway Biology Options"], {
    takenCodes: ["BIOLOGY 205", "BIOLOGY 207", "CHEM 210"],
    groupHitCodes: ["BIOLOGY 205", "BIOLOGY 207"],
    creditByCode: { "BIOLOGY 205": 3, "BIOLOGY 207": 4 },
  });
  assert.equal(r.complete, true);
});

test("manual Additional stays incomplete without override", () => {
  const r = isGroupComplete(bhsRules.groupRules["Additional Courses"], {
    takenCodes: ["BIOLOGY 305"],
  });
  assert.equal(r.complete, false);
  assert.equal(r.reason, "manual");
});

test("minCredits from clause counts taken electives", () => {
  const clause = {
    minCredits: 5,
    from: ["CHEM 351", "CHEM 352", "CHEM 402"],
  };
  const taken = toTakenSet(["CHEM 351", "CHEM 352"]);
  assert.equal(
    isClauseSatisfied(clause, taken, { "CHEM 351": 3, "CHEM 352": 3 }),
    true
  );
  assert.equal(
    isClauseSatisfied(clause, toTakenSet(["CHEM 351"]), {
      "CHEM 351": 3,
    }),
    false
  );
});

test("BHS: two Group A courses do not also complete Group D", () => {
  const taken = toTakenSet(["BIOLOGY 205", "BIOLOGY 207"]);
  const allocated = allocateGroupHits({
    groupNames: Object.keys(bhsMajor.requirementGroups),
    groupRules: bhsRules.groupRules,
    getEligible: (g) => bhsEligible(g, taken),
    creditByCode: { "BIOLOGY 205": 3, "BIOLOGY 207": 4 },
  });

  const groupA = "Group A: Gateway Biology Options";
  const groupD = "Group D - Biology Elective";
  assert.equal(
    isGroupComplete(bhsRules.groupRules[groupA], {
      groupHitCodes: allocated.get(groupA),
      creditByCode: { "BIOLOGY 205": 3, "BIOLOGY 207": 4 },
    }).complete,
    true
  );
  assert.equal(
    isGroupComplete(bhsRules.groupRules[groupD], {
      groupHitCodes: allocated.get(groupD) || [],
      creditByCode: { "BIOLOGY 205": 3, "BIOLOGY 207": 4 },
    }).complete,
    false
  );
  assert.deepEqual([...(allocated.get(groupD) || [])].sort(), []);
});

test("BHS: third Group A-eligible course can fill Group D", () => {
  const taken = toTakenSet(["BIOLOGY 205", "BIOLOGY 207", "BIOLOGY 222"]);
  const allocated = allocateGroupHits({
    groupNames: Object.keys(bhsMajor.requirementGroups),
    groupRules: bhsRules.groupRules,
    getEligible: (g) => bhsEligible(g, taken),
    creditByCode: {
      "BIOLOGY 205": 3,
      "BIOLOGY 207": 4,
      "BIOLOGY 222": 3,
    },
  });
  const groupD = "Group D - Biology Elective";
  assert.equal(
    isGroupComplete(bhsRules.groupRules[groupD], {
      groupHitCodes: allocated.get(groupD),
      creditByCode: { "BIOLOGY 222": 3 },
    }).complete,
    true
  );
  assert.equal((allocated.get(groupD) || []).length, 1);
});

test("BHS Lab mayOverlap uses courses already counted elsewhere", () => {
  // BIOLOGY 207 is both Group A and Lab
  const taken = toTakenSet(["BIOLOGY 205", "BIOLOGY 207"]);
  const allocated = allocateGroupHits({
    groupNames: Object.keys(bhsMajor.requirementGroups),
    groupRules: bhsRules.groupRules,
    getEligible: (g) => bhsEligible(g, taken),
    creditByCode: { "BIOLOGY 205": 3, "BIOLOGY 207": 4 },
  });
  assert.equal(
    isGroupComplete(bhsRules.groupRules["Lab Requirement"], {
      groupHitCodes: allocated.get("Lab Requirement"),
    }).complete,
    true
  );
  // Still must not free Group A courses for D
  assert.equal((allocated.get("Group D - Biology Elective") || []).length, 0);
});
