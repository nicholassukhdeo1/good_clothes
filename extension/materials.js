// materials.js
// Deterministic materials scoring. Runs locally in the page — no network, always works.
// This is your reliable demo spine: even if the backend is down, the badge still scores.
// Loaded BEFORE content.js (see manifest), so these globals are available there.

// Higher = more durable / lower environmental cost.
const FIBER_WEIGHTS = {
  // Natural / plant-based textiles
  "organic cotton": 95,
  linen: 90,
  hemp: 90,
  bamboo: 85,
  cork: 85,
  cotton: 82,
  wool: 82,
  silk: 78,
  cashmere: 76,
  down: 74,
  feather: 60,
  tencel: 74,
  lyocell: 72,
  cupro: 58,
  modal: 58,
  viscose: 46,
  rayon: 44,

  // Leather & animal-derived (durable but impact varies)
  leather: 70,
  nappa: 70,
  "full-grain leather": 72,
  "pony hair": 60,
  suede: 66,
  nubuck: 66,
  shearling: 68,
  fur: 30,

  // Metals (durable, mining impact offset by longevity)
  titanium: 82,
  gold: 78,
  "sterling silver": 78,
  silver: 76,
  "stainless steel": 72,
  steel: 68,
  brass: 52,
  copper: 52,
  "gold-plated": 48,
  "silver-plated": 48,
  pewter: 50,
  zinc: 48,

  // Natural rubber / sustainable
  "natural rubber": 62,
  rubber: 45,
  cork: 85,

  // Recycled synthetics (better than virgin)
  "recycled polyester": 52,
  "recycled nylon": 55,
  "recycled cotton": 88,
  "recycled wool": 80,

  // Synthetics
  acetate: 50,
  neoprene: 36,
  fleece: 34,
  mesh: 32,
  elastane: 34,
  spandex: 34,
  nylon: 30,
  polyamide: 30,
  polyester: 24,
  acrylic: 20,
  pvc: 14,
  "faux leather": 22,
  "vegan leather": 22,
};
const DEFAULT_WEIGHT = 40;

// Normalize aliases before lookup
function normalizeFiber(raw) {
  const s = raw.toLowerCase().trim();
  const aliases = {
    "full grain leather": "full-grain leather",
    "genuine leather": "leather",
    "lambskin": "leather",
    "calfskin": "leather",
    "cowhide": "leather",
    "goatskin": "leather",
    "pigskin": "leather",
    "patent leather": "leather",
    "saffiano leather": "leather",
    "pebbled leather": "leather",
    "grained leather": "leather",
    "smooth leather": "leather",
    "vegtan leather": "leather",
    "veg tan": "leather",
    "bovine leather": "leather",
    "calf leather": "leather",
    "nappa leather": "nappa",
    "nubuck leather": "nubuck",
    "split leather": "leather",
    "microfiber": "polyester",
    "microfibre": "polyester",
    "lyocell": "lyocell",
    "tencel lyocell": "tencel",
    "sterling": "sterling silver",
    "925 silver": "sterling silver",
    "925 sterling": "sterling silver",
    "18k gold": "gold",
    "14k gold": "gold",
    "9k gold": "gold",
    "gold plated": "gold-plated",
    "gold-plated brass": "gold-plated",
    "gold-plated steel": "gold-plated",
    "silver plated": "silver-plated",
    "stainless": "stainless steel",
    "ss": null, // too ambiguous
    "polyurethane": "faux leather",
    "pu leather": "faux leather",
    "bonded leather": "faux leather",
    "spandex": "elastane",
    "lycra": "elastane",
    "down fill": "down",
    "duck down": "down",
    "goose down": "down",
    "down feather": "down",
  };
  return aliases[s] !== undefined ? aliases[s] : s;
}

function weightFor(raw) {
  const fiber = normalizeFiber(raw);
  if (!fiber) return DEFAULT_WEIGHT;
  if (FIBER_WEIGHTS[fiber] != null) return FIBER_WEIGHTS[fiber];
  for (const key of Object.keys(FIBER_WEIGHTS)) {
    if (fiber.includes(key) || key.includes(fiber)) return FIBER_WEIGHTS[key];
  }
  return DEFAULT_WEIGHT;
}

// Parse "80% Cotton, 20% Polyester" → [{fiber, pct}]
function parsePercentages(text) {
  const out = [];
  const re = /(\d+(?:\.\d+)?)\s*%\s*([a-zA-Z][a-zA-Z\s\-]*)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const pct = parseFloat(m[1]);
    const fiber = m[2].trim();
    if (pct > 0 && pct <= 100) out.push({ fiber, pct });
  }
  return out;
}

// All bare material keywords we can recognize without a percentage.
// Order matters: more specific phrases first so "stainless steel" matches before "steel",
// "full-grain leather" before "leather", etc.
const BARE_KEYWORDS = [
  // Metals – specific first
  "sterling silver", "925 sterling", "925 silver", "18k gold", "14k gold", "9k gold",
  "gold-plated brass", "gold-plated steel", "gold plated", "silver plated",
  "stainless steel", "titanium", "brass", "copper", "silver", "gold", "pewter", "zinc",
  // Leather – all common synonyms SSENSE uses
  "full-grain leather", "full grain leather",
  "nappa leather", "nubuck leather", "patent leather", "saffiano leather",
  "pebbled leather", "grained leather", "smooth leather", "suede leather",
  "lambskin leather", "calfskin leather", "goatskin leather", "cowhide leather",
  "genuine leather", "veg tan leather", "bovine leather",
  "lambskin", "calfskin", "goatskin", "cowhide", "pigskin",
  "pony hair", "shearling", "shearling leather",
  "leather", "suede", "nubuck", "nappa",
  // Rubber / synthetics
  "natural rubber", "vulcanized rubber", "rubber",
  "faux leather", "vegan leather", "pu leather",
  // Textiles (no %)
  "fleece", "denim", "tweed", "corduroy", "canvas", "felt", "velvet", "satin",
  "chiffon", "lace", "jacquard", "brocade", "jersey", "mesh",
  // Down / fill
  "goose down", "duck down", "down feather", "down fill", "down",
  // Optical / specialist
  "acetate", "neoprene",
  // Wood / naturals
  "wood", "cork", "bamboo",
];

// Extract material candidates from a text block that has no percentage notation.
// Tries "Label: Material" patterns first, then scans for bare keywords.
function parseBare(text) {
  if (!text) return [];
  const lower = text.toLowerCase();

  // "Upper: Leather" / "Material: Stainless Steel" / "Shell: Nylon" patterns
  const labelRe = /(?:upper|outer|shell|lining|sole|insole|fill|material|composition|fabric|body|hardware|closure|chain|pendant|frame|lens|strap|trim|detail)s?\s*[:–-]\s*([^,\n·•.]{2,60})/gi;
  const labeled = [];
  let lm;
  while ((lm = labelRe.exec(text)) !== null) {
    const candidate = lm[1].trim();
    for (const kw of BARE_KEYWORDS) {
      if (candidate.toLowerCase().includes(kw)) {
        labeled.push({ fiber: kw, pct: 100 / (labeled.length + 1) });
        break;
      }
    }
  }
  if (labeled.length) {
    // Renormalize to 100%
    const total = labeled.reduce((s, p) => s + p.pct, 0);
    labeled.forEach(p => { p.pct = (p.pct / total) * 100; });
    return labeled;
  }

  // Plain keyword scan — return first match, treat as 100%
  for (const kw of BARE_KEYWORDS) {
    if (lower.includes(kw)) return [{ fiber: kw, pct: 100 }];
  }
  return [];
}

function parseComposition(text) {
  if (!text) return [];
  const pct = parsePercentages(text);
  if (pct.length) return pct;
  return parseBare(text);
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

window.GC_scoreMaterials = scoreMaterials;
