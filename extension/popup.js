// popup.js — shows the last score the content script stored + the active style
// lane. Drop-in replacement: same storage reads as the original, restyled output.

function colorFor(s) {
  if (s == null) return "#a8a399";
  if (s >= 70) return "#3e6b4e";
  if (s >= 45) return "#b5832e";
  return "#a8463a";
}
function verdictFor(s) {
  if (s == null) return "";
  if (s >= 70) return "Worth it";
  if (s >= 45) return "Borderline";
  return "Think twice";
}

// 270° arc score ring as inline SVG.
function ringSvg(score, size) {
  const t = 4, r = (size - t) / 2, cx = size / 2;
  const circ = 2 * Math.PI * r, arcLen = circ * 0.75, rot = `rotate(135 ${cx} ${cx})`;
  const has = typeof score === "number";
  const stroke = colorFor(has ? score : null);
  const pct = has ? Math.max(0, Math.min(100, score)) / 100 : 0;
  return (
    `<div class="ring-wrap" style="width:${size}px;height:${size}px">` +
    `<svg width="${size}" height="${size}" style="display:block">` +
    `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="#e9e6dd" stroke-width="${t}" stroke-linecap="round" stroke-dasharray="${arcLen} ${circ}" transform="${rot}"/>` +
    (has ? `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${stroke}" stroke-width="${t}" stroke-linecap="round" stroke-dasharray="${arcLen * pct} ${circ}" transform="${rot}"/>` : "") +
    `</svg>` +
    `<div class="ring-num" style="font-size:${Math.round(size * 0.36)}px;color:${has ? "#1a1916" : "#908d82"}">${has ? Math.round(score) : "·"}</div>` +
    `</div>`
  );
}

function metric(label, value) {
  const has = typeof value === "number";
  const right = has ? `<b>${value}</b> / 100` : "—";
  return (
    `<div class="metric"><div class="metric-top">` +
    `<span class="metric-label">${label}</span><span class="metric-val">${right}</span></div>` +
    `<div class="bar"><span style="width:${has ? value : 0}%;background:${colorFor(has ? value : null)}"></span></div></div>`
  );
}

// active style lane
chrome.storage.sync.get({ gc_pref: window.GC_DEFAULT_PREF }, ({ gc_pref }) => {
  document.getElementById("pref").textContent = window.GC_PREF_LABEL[gc_pref] || gc_pref;
});
document.getElementById("change").addEventListener("click", () => {
  chrome.tabs.create({ url: chrome.runtime.getURL("onboarding.html") });
});

// last score
chrome.storage.local.get("gc_last", ({ gc_last }) => {
  const out = document.getElementById("out");
  if (!gc_last) return;
  const r = gc_last.research || {};
  const brand = gc_last.brand || r.brand || "This item";
  const alts = (gc_last.alternatives && gc_last.alternatives.alternatives) || [];
  out.classList.remove("muted");
  out.innerHTML =
    `<div class="hero">${ringSvg(gc_last.final, 48)}` +
    `<div><div class="verdict">${verdictFor(gc_last.final)}</div>` +
    `<div class="brand">${brand}</div></div></div>` +
    `<div class="divider"></div>` +
    metric("Materials", gc_last.materials && gc_last.materials.score) +
    metric("Ethics", r.ethics_score) +
    metric("Ownership", r.ownership_score) +
    (alts.length
      ? `<div class="alts-h">Better options</div>` +
        alts
          .map(
            (a) =>
              `<div class="alt"><a href="${a.url}" target="_blank">${a.name}</a> · ${a.est_score}/100` +
              `<div class="alt-why">${a.why}</div></div>`
          )
          .join("")
      : "");
});
