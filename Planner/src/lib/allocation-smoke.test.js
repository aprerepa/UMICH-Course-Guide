import { readFileSync, readdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test from "node:test";

import { allocateGroupHits, toTakenSet } from "./completion.js";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const rulesDir = join(root, "config/rules");
const majorsDir = join(root, "config/majors");

test("allocateGroupHits runs for every live rules+majors pair", () => {
  let ok = 0;
  let skip = 0;
  for (const file of readdirSync(rulesDir).filter((f) => f.endsWith(".json"))) {
    const rules = JSON.parse(readFileSync(join(rulesDir, file), "utf8"));
    const id = rules.id || file.replace(/\.json$/, "");
    let major;
    try {
      major = JSON.parse(readFileSync(join(majorsDir, `${id}.json`), "utf8"));
    } catch {
      try {
        major = JSON.parse(readFileSync(join(majorsDir, file), "utf8"));
      } catch {
        skip += 1;
        continue;
      }
    }
    const sample = Object.values(major.requirementGroups || {})
      .flat()
      .filter((c) => typeof c === "string")
      .slice(0, 12);
    const taken = toTakenSet(sample);
    const allocated = allocateGroupHits({
      groupNames: Object.keys(major.requirementGroups || {}),
      groupRules: rules.groupRules || {},
      getEligible: (g) => {
        const list = major.requirementGroups?.[g] || [];
        return [...taken].filter((c) => list.includes(c));
      },
      creditByCode: {},
    });
    assert.ok(allocated instanceof Map);
    ok += 1;
  }
  assert.ok(ok > 50, `expected many majors, got ok=${ok} skip=${skip}`);
});
