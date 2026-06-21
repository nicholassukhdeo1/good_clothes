// background.js (MV3 service worker)
// The content script CANNOT reliably fetch your backend directly (CORS + page CSP).
// Route every network call through here. This is the single most common extension
// gotcha — get this round-trip working FIRST (Block 1).

// Backend URL. Default = deployed (works on any machine). For local dev, flip to localhost.
const BACKEND = "https://good-clothes-backend.onrender.com";
// const BACKEND = "http://localhost:8000";

// On first install, open the preferences page so the user picks a style lane.
chrome.runtime.onInstalled.addListener((details) => {
  if (details.reason === "install") {
    chrome.tabs.create({ url: chrome.runtime.getURL("onboarding.html") });
  }
});

// Single relay for both endpoints — content.js picks the path via msg.type.
const ROUTES = {
  RESEARCH: (m) => ["/research", { brand: m.brand }],
  ALTERNATIVES: (m) => [
    "/alternatives",
    { brand: m.brand, title: m.title, score: m.score, composition: m.composition, image: m.image, pref: m.pref || "" },
  ],
};

// Detect SPA navigation on SSENSE (pushState / replaceState) from the browser
// level — content scripts can't intercept page-level history calls reliably
// because they run in an isolated JS world.
chrome.webNavigation.onHistoryStateUpdated.addListener(
  (details) => {
    if (/\/product\//.test(details.url)) {
      // Tell the content script a new product page has loaded
      chrome.tabs.sendMessage(details.tabId, { type: "GC_NAV", url: details.url }).catch(() => {});
    } else {
      // Navigated away from a product — tell the badge to hide
      chrome.tabs.sendMessage(details.tabId, { type: "GC_NAV_AWAY" }).catch(() => {});
    }
  },
  { url: [{ hostSuffix: "ssense.com" }] }
);

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  const route = ROUTES[msg.type];
  if (!route) return;
  const [path, body] = route(msg);
  fetch(`${BACKEND}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
    .then((r) => r.json())
    .then((data) => sendResponse(data))
    .catch((e) => sendResponse({ error: String(e) }));
  return true; // IMPORTANT: keeps the message channel open for the async sendResponse
});
