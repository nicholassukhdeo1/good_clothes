// background.js (MV3 service worker)
// The content script CANNOT reliably fetch your backend directly (CORS + page CSP).
// Route every network call through here. This is the single most common extension
// gotcha — get this round-trip working FIRST (Block 1).

const BACKEND = "http://localhost:8000"; // TODO: swap for your deployed URL before the demo

// Single relay for both endpoints — content.js picks the path via msg.type.
const ROUTES = {
  RESEARCH: (m) => ["/research", { brand: m.brand }],
  ALTERNATIVES: (m) => [
    "/alternatives",
    { brand: m.brand, title: m.title, score: m.score, composition: m.composition },
  ],
};

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
