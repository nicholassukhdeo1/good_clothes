// popup.js — shows the last score the content script stored + the current style lane.
chrome.storage.sync.get({ gc_pref: window.GC_DEFAULT_PREF }, ({ gc_pref }) => {
  document.getElementById("pref").textContent = window.GC_PREF_LABEL[gc_pref] || gc_pref;
});
document.getElementById("change").addEventListener("click", () => {
  chrome.tabs.create({ url: chrome.runtime.getURL("onboarding.html") });
});

chrome.storage.local.get("gc_last", ({ gc_last }) => {
  const out = document.getElementById("out");
  if (!gc_last) return;
  const r = gc_last.research || {};
  const alts = gc_last.alternatives?.alternatives || [];
  out.classList.remove("muted");
  out.innerHTML = `
    <div><b>Overall: ${gc_last.final ?? "—"}/100</b></div>
    <div>Materials: ${gc_last.materials?.score ?? "—"}/100</div>
    <div>Ethics: ${r.ethics_score ?? "—"}/100</div>
    <div>Ownership: ${r.ownership_score ?? "—"}/100</div>
    ${r.summary ? `<div style="margin-top:6px;color:#5f6368">${r.summary}</div>` : ""}
    ${
      alts.length
        ? `<div style="margin-top:10px;font-weight:700;color:#1e8e3e">Better options</div>` +
          alts
            .map(
              (a) =>
                `<div style="margin-top:4px"><a href="${a.url}" target="_blank">${a.name}</a> · ${a.est_score}/100<br><span style="color:#5f6368;font-size:12px">${a.why}</span></div>`
            )
            .join("")
        : ""
    }
  `;
});
