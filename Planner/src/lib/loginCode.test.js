import assert from "node:assert/strict";
import test from "node:test";

import {
  formatLoginCode,
  generateLoginCode,
  isValidLoginCode,
  loginCodeFromAuthEmail,
  loginCodeToAuthEmail,
  normalizeLoginCode,
} from "./loginCode.js";

test("generateLoginCode produces umich- prefix and 12 suffix chars", () => {
  const code = generateLoginCode();
  assert.match(code, /^umich-[a-z0-9]{12}$/);
  assert.equal(isValidLoginCode(code), true);
});

test("normalize accepts with or without umich- prefix", () => {
  assert.equal(
    normalizeLoginCode("umich-a3k9m2x7p1q4"),
    "umich-a3k9m2x7p1q4"
  );
  assert.equal(normalizeLoginCode("a3k9m2x7p1q4"), "umich-a3k9m2x7p1q4");
});

test("auth email round trip", () => {
  const raw = "umich-a3k9m2x7p1q4";
  const email = loginCodeToAuthEmail(raw);
  assert.equal(email, "a3k9m2x7p1q4@example.com");
  assert.equal(loginCodeFromAuthEmail(email), formatLoginCode(raw));
});

test("isValidLoginCode rejects short codes", () => {
  assert.equal(isValidLoginCode("umich-short"), false);
  assert.equal(isValidLoginCode("umich-a3k9m2x7p1q4"), true);
});
