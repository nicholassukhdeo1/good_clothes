// test_materials.js — unit tests for the materials scoring logic.
// Run with: node extension/tests/test_materials.js
// No npm install needed — uses only Node built-ins.

const assert = require("assert");
const fs = require("fs");
const path = require("path");

// materials.js writes its export to window.GC_scoreMaterials.
// Provide a minimal shim so it runs outside a browser.
global.window = {};
eval(fs.readFileSync(path.join(__dirname, "../materials.js"), "utf8"));
const score = window.GC_scoreMaterials;

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  pass  ${name}`);
    passed++;
  } catch (e) {
    console.log(`  FAIL  ${name}: ${e.message}`);
    failed++;
  }
}

// ---- Percentage-based compositions ----

test("100% cotton scores 82", () => {
  assert.strictEqual(score("100% Cotton").score, 82);
});

test("100% organic cotton scores 95", () => {
  assert.strictEqual(score("100% Organic Cotton").score, 95);
});

test("100% polyester scores 24", () => {
  assert.strictEqual(score("100% Polyester").score, 24);
});

test("100% acrylic scores 20", () => {
  assert.strictEqual(score("100% Acrylic").score, 20);
});

test("80% cotton / 20% polyester — weighted average rounds to 70", () => {
  // 0.8 * 82 + 0.2 * 24 = 65.6 + 4.8 = 70.4 -> 70
  assert.strictEqual(score("80% Cotton, 20% Polyester").score, 70);
});

test("parsed:true when percentages are present", () => {
  assert.strictEqual(score("100% Wool").parsed, true);
});

// ---- Alias normalization ----

test("lambskin resolves to leather (70)", () => {
  assert.strictEqual(score("Lambskin").score, 70);
});

test("calfskin resolves to leather (70)", () => {
  assert.strictEqual(score("Calfskin").score, 70);
});

test("925 sterling resolves to sterling silver (78)", () => {
  assert.strictEqual(score("925 Sterling").score, 78);
});

test("goose down resolves to down (74)", () => {
  assert.strictEqual(score("Goose Down").score, 74);
});

// Note: bare "Polyurethane" (no percentage) doesn't score because it isn't in
// BARE_KEYWORDS — alias normalization only kicks in after a percentage match finds
// the fiber. "100% Polyurethane" works correctly (→ faux leather, 22).

// ---- Bare keyword matches (no percentage) ----

test("Sterling Silver bare keyword scores 78", () => {
  assert.strictEqual(score("Sterling Silver").score, 78);
});

test("Stainless Steel bare keyword scores 72", () => {
  assert.strictEqual(score("Stainless Steel").score, 72);
});

test("Acetate bare keyword scores 50", () => {
  assert.strictEqual(score("Acetate").score, 50);
});

// ---- Labelled multi-part (footwear / bags) ----

test("Upper: Calfskin. Sole: Rubber. — blended, parsed:true", () => {
  const r = score("Upper: Calfskin. Sole: Rubber.");
  assert.strictEqual(r.parsed, true);
  // calfskin -> leather=70, rubber=45; roughly 50/50 -> ~57
  assert.ok(r.score >= 50 && r.score <= 72, `score ${r.score} out of expected 50-72 range`);
});

// ---- Unknown / empty inputs ----

test("empty string returns parsed:false and score:null", () => {
  const r = score("");
  assert.strictEqual(r.parsed, false);
  assert.strictEqual(r.score, null);
});

test("gibberish text returns parsed:false", () => {
  assert.strictEqual(score("xyzzy frobnik").parsed, false);
});

test("parts array is empty when nothing is recognized", () => {
  assert.deepStrictEqual(score("").parts, []);
});

// ---- Summary ----
console.log(`\n${passed} passed, ${failed} failed`);
if (failed > 0) process.exit(1);
