import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
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
