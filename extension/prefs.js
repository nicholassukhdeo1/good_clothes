// prefs.js — single source of truth for the style lanes.
// Loaded (before the page/content script) by onboarding, popup, and content.js so the
// dropdown, the saved value, and the request all stay in sync. Keys MUST match the
// PREF_GUIDANCE map in backend/alternatives.py.
window.GC_PREFS = [
  {
    key: "balanced",
    label: "Best overall",
    hint: "The most conscious pick at any price — no style bias.",
  },
  {
    key: "avant_garde",
    label: "Avant-garde / designer",
    hint: "Editorial, high-fashion labels — the kind i-D or Vogue feature (Rick Owens, Lemaire…).",
  },
  {
    key: "affordable",
    label: "Affordable / accessible",
    hint: "Budget-friendly, widely-available brands that still beat the original on ethics.",
  },
  {
    key: "streetwear",
    label: "Streetwear",
    hint: "Elevated, more-sustainable streetwear labels.",
  },
  {
    key: "minimal",
    label: "Minimal / timeless",
    hint: "Understated labels known for durable, long-lasting basics.",
  },
];

window.GC_DEFAULT_PREF = "balanced";

// key -> short label, for compact display in the badge/popup.
window.GC_PREF_LABEL = window.GC_PREFS.reduce((m, p) => ((m[p.key] = p.label), m), {});
