// background.js (MV3 service worker)
// The content script CANNOT reliably fetch your backend directly (CORS + page CSP).
// Route every network call through here. This is the single most common extension
// gotcha — get this round-trip working FIRST (Block 1).

const BACKEND = "http://localhost:8000"; // TODO: swap for your deployed URL before the demo

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === "RESEARCH") {
    fetch(`${BACKEND}/research`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ brand: msg.brand }),
    })
      .then((r) => r.json())
      .then((data) => sendResponse(data))
      .catch((e) => sendResponse({ error: String(e) }));
    return true; // IMPORTANT: keeps the message channel open for the async sendResponse
  }
});
