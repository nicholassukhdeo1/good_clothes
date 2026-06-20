// materials.js
// Deterministic materials scoring. Runs locally in the page — no network, always works.
// This is your reliable demo spine: even if the backend is down, the badge still scores.
// Loaded BEFORE content.js (see manifest), so these globals are available there.

// Higher = more durable / lower environmental cost. Tune these freely; judges like
// seeing a defensible rubric, so be ready to explain why polyester < cotton.
const FIBER_WEIGHTS = {
  "organic cotton": 95,
  linen: 90,
  hemp: 90,
  cotton: 85,
  wool: 85,
  silk: 80,
  cashmere: 78,
  tencel: 72,
  leather: 70,
  lyocell: 68,
  modal: 60,
  viscose: 50,
  rayon: 50,
  "recycled polyester": 48,
  elastane: 35,
  spandex: 35,
  nylon: 30,
  polyamide: 30,
  polyester: 25,
  acrylic: 20,
};
const DEFAULT_WEIGHT = 40; // unknown fiber -> neutral-ish

// Parse strings like "80% Cotton, 20% Polyester" into [{ fiber, pct }].
function parseComposition(text) {
  if (!text) return [];
  const out = [];
  const re = /(\d+(?:\.\d+)?)\s*%\s*([a-zA-Z][a-zA-Z\s]*)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const pct = parseFloat(m[1]);
    const fiber = m[2].trim().toLowerCase();
    if (pct > 0) out.push({ fiber, pct });
  }
  return out;
}

function weightFor(fiber) {
  if (FIBER_WEIGHTS[fiber] != null) return FIBER_WEIGHTS[fiber];
  // loose contains-match so "100% supima cotton" still finds "cotton"
  for (const key of Object.keys(FIBER_WEIGHTS)) {
    if (fiber.includes(key)) return FIBER_WEIGHTS[key];
  }
  return DEFAULT_WEIGHT;
}

// Returns { score (0-100), parts:[{fiber,pct,weight}], parsed:boolean }
function scoreMaterials(text) {
  const parts = parseComposition(text);
  if (parts.length === 0) return { score: null, parts: [], parsed: false };
  const totalPct = parts.reduce((s, p) => s + p.pct, 0) || 100;
  let acc = 0;
  for (const p of parts) {
    p.weight = weightFor(p.fiber);
    acc += p.weight * (p.pct / totalPct);
  }
  return { score: Math.round(acc), parts, parsed: true };
}

// expose to content.js (same content-script execution context)
window.GC_scoreMaterials = scoreMaterials;
