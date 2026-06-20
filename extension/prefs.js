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

// Backend base — extension pages (onboarding/popup) hit /prefs directly; it's in
// host_permissions so the fetch is allowed. Default = deployed; flip to localhost for dev.
window.GC_BACKEND = "https://good-clothes-backend.onrender.com";
// window.GC_BACKEND = "http://localhost:8000";

// A stable anonymous id per install, so the backend can key preferences without any
// login. Generated once and kept in local storage.
window.GC_getUid = function (cb) {
  chrome.storage.local.get("gc_uid", ({ gc_uid }) => {
    if (gc_uid) return cb(gc_uid);
    const id =
      (self.crypto && crypto.randomUUID && crypto.randomUUID()) ||
      `u_${Date.now()}_${Math.random().toString(16).slice(2)}`;
    chrome.storage.local.set({ gc_uid: id }, () => cb(id));
  });
};
