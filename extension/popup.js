// popup.js — shows the last score the content script stored.
chrome.storage.local.get("gc_last", ({ gc_last }) => {
  const out = document.getElementById("out");
  if (!gc_last) return;
  const r = gc_last.research || {};
  out.classList.remove("muted");
  out.innerHTML = `
    <div><b>Overall: ${gc_last.final ?? "—"}/100</b></div>
    <div>Materials: ${gc_last.materials?.score ?? "—"}/100</div>
    <div>Ethics: ${r.ethics_score ?? "—"}/100</div>
    <div>Ownership: ${r.ownership_score ?? "—"}/100</div>
    ${r.summary ? `<div style="margin-top:6px;color:#5f6368">${r.summary}</div>` : ""}
  `;
});
