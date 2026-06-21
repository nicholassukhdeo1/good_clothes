// content.js — good_clothes (editorial redesign).
// Drop-in replacement. Scraping, materials scoring, backend messaging and SPA
// navigation handling are UNCHANGED from the original — only the badge's visual
// rendering (renderBadge / the ring / breakdown / alternatives) was restyled.

// ---------- 1. SCRAPE (tuned for SSENSE) ----------

// Matches percentage-based compositions: "80% Cotton", "100% Stainless Steel", etc.
const FIBER_RE =
  /\b\d{1,3}\s*%\s*(?:organic |recycled |supima |pima )?(?:cotton|linen|hemp|wool|silk|cashmere|tencel|lyocell|modal|viscose|rayon|polyester|polyamide|nylon|elastane|spandex|acrylic|leather|suede|nubuck|cupro|down|feather|rubber|polyurethane|neoprene|acetate)/i;

// Bare material recognition — metals, leathers, fill, rubber, textiles, optical.
// Listed longest-first so "stainless steel" matches before "steel".
const BARE_MATERIAL_RE =
  /\b(?:sterling silver|925 sterling|925 silver|18k gold|14k gold|9k gold|gold[- ]plated(?:\s+\w+)?|silver[- ]plated|stainless steel|full[- ]grain leather|nappa leather|patent leather|saffiano leather|grained leather|calfskin leather|lambskin leather|genuine leather|pony hair|goose down|duck down|down feather|down fill|natural rubber|vulcanized rubber|faux leather|vegan leather|pu leather|titanium|brass|copper|silver|gold|pewter|zinc|steel|rubber|leather|suede|nubuck|shearling|fleece|denim|tweed|corduroy|canvas|velvet|satin|chiffon|lace|jersey|mesh|felt|acetate|neoprene|cork|bamboo|wood|down)\b/i;

// "Upper: Leather, Sole: Rubber" — labelled multi-part descriptions
const LABELLED_RE =
  /(?:upper|outer|shell|lining|sole|insole|fill|material|composition|fabric|body|hardware|closure|chain|pendant|frame|lens|strap|trim)\s*[:–\-]\s*([^,\n·•]{2,60})/i;

function findBrand() {
  const designer = document.querySelector('a[href*="/designers/"]');
  if (designer && designer.innerText.trim()) return designer.innerText.trim();
  const h1a = document.querySelector("h1 a");
  if (h1a && h1a.innerText.trim()) return h1a.innerText.trim();
  const h1 = document.querySelector("h1");
  if (h1 && h1.innerText.trim()) return h1.innerText.trim();
  return "Unknown";
}

function findComposition() {
  let pctBest = "";      // has explicit X%
  let labelBest = "";    // has "Upper: Leather" style label
  let bareBest = "";     // bare material keyword only

  const els = document.querySelectorAll("li, p, span, div, td");
  for (const el of els) {
    if (el.children.length !== 0) continue;
    const t = el.innerText && el.innerText.trim();
    if (!t || t.length > 300) continue;

    if (FIBER_RE.test(t)) {
      // Prefer the shortest percentage-bearing string (fewest extra words)
      if (!pctBest || t.length < pctBest.length) pctBest = t;
    } else if (!labelBest && LABELLED_RE.test(t)) {
      labelBest = t;
    } else if (!bareBest && BARE_MATERIAL_RE.test(t) && t.length < 150) {
      bareBest = t;
    }
  }

  // Fallback: scan the og:description or page title for bare material keywords
  // (catches jewelry/accessories where the material is only in the product name)
  if (!pctBest && !labelBest && !bareBest) {
    const meta = document.querySelector('meta[name="description"], meta[property="og:description"]');
    const metaText = (meta && meta.content) || document.title || "";
    if (BARE_MATERIAL_RE.test(metaText)) bareBest = metaText.slice(0, 200);
  }

  return pctBest || labelBest || bareBest;
}

function findImage() {
  const og = document.querySelector('meta[property="og:image"]');
  if (og && og.content) return og.content;
  let best = "";
  let area = 0;
  for (const img of document.querySelectorAll("img")) {
    const a = (img.naturalWidth || 0) * (img.naturalHeight || 0);
    if (a > area && img.src) {
      area = a;
      best = img.src;
    }
  }
  return best;
}

function scrape() {
  return {
    brand: findBrand(),
    composition: findComposition(),
    image: findImage(),
    title: document.title,
    url: location.href,
  };
}

// ---------- 2. BADGE ----------
function ensureBadge() {
  let el = document.getElementById("gc-badge");
  if (!el) {
    el = document.createElement("div");
    el.id = "gc-badge";
    document.body.appendChild(el);
  }
  return el;
}

// Editorial, muted score colors — NOT traffic-light.
function colorFor(score) {
  if (score == null) return "#a8a399";
  if (score >= 70) return "#3e6b4e";
  if (score >= 45) return "#b5832e";
  return "#a8463a";
}
function verdictFor(score) {
  if (score == null) return "";
  if (score >= 70) return "Worth it";
  if (score >= 45) return "Borderline";
  return "Think twice";
}

// Build the 270° arc score ring as inline SVG (the data-viz centerpiece).
function ringSvg(score, size, loading) {
  const thickness = 4;
  const r = (size - thickness) / 2;
  const cx = size / 2;
  const circ = 2 * Math.PI * r;
  const arcLen = circ * 0.75; // 270°
  const rot = `rotate(135 ${cx} ${cx})`;
  const stroke = colorFor(loading ? null : score);
  const track = `<circle cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="#e9e6dd" stroke-width="${thickness}" stroke-linecap="round" stroke-dasharray="${arcLen} ${circ}" transform="${rot}"/>`;
  let value;
  if (loading) {
    // No static SVG transform — let CSS handle the rotation via transform-box:fill-box
    value = `<circle class="gc-arc-load" cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${stroke}" stroke-width="${thickness}" stroke-linecap="round" stroke-dasharray="${circ * 0.28} ${circ}"/>`;
  } else {
    const pct = Math.max(0, Math.min(100, score)) / 100;
    value = `<circle class="gc-arc-val" cx="${cx}" cy="${cx}" r="${r}" fill="none" stroke="${stroke}" stroke-width="${thickness}" stroke-linecap="round" stroke-dasharray="${arcLen * pct} ${circ}" transform="${rot}"/>`;
  }
  const numeral = loading ? "·" : Math.round(score);
  const numColor = loading ? "#908d82" : "#1a1916";
  return (
    `<div class="gc-ring-wrap" style="width:${size}px;height:${size}px">` +
    `<svg width="${size}" height="${size}" style="display:block">${track}${value}</svg>` +
    `<div class="gc-ring-num" style="font-size:${Math.round(size * 0.36)}px;color:${numColor}">${numeral}</div>` +
    `</div>`
  );
}

function metricRow(label, value, hint) {
  const has = typeof value === "number";
  const right = has
    ? `<b>${value}</b> / 100`
    : `<span class="gc-metric-hint">${hint || "—"}</span>`;
  const barW = has ? Math.max(0, Math.min(100, value)) : 0;
  const barColor = colorFor(has ? value : null);
  return (
    `<div class="gc-metric">` +
    `<div class="gc-metric-top"><span class="gc-metric-label">${label}</span>` +
    `<span class="gc-metric-val">${right}</span></div>` +
    `<div class="gc-bar"><span style="width:${barW}%;background:${barColor}"></span></div>` +
    `</div>`
  );
}

const ALT_THRESHOLD = 60;

function altsHtml(alts) {
  if (!alts) return "";
  if (alts.loading)
    return `<div class="gc-alts"><div class="gc-alts-h">Finding better options…</div></div>`;
  if (!alts.alternatives || !alts.alternatives.length) return "";
  const rows = alts.alternatives
    .map(
      (a) =>
        `<div class="gc-alt">` +
        `<a href="${a.url}" target="_blank">${a.name} <span class="gc-alt-shop">Shop ↗</span></a>` +
        `<span class="gc-alt-score" style="color:${colorFor(a.est_score)}">${a.est_score}</span>` +
        (a.why ? `<div class="gc-alt-why">${a.why}</div>` : "") +
        `</div>`
    )
    .join("");
  const look = alts.look ? `<div class="gc-alts-look">matching: ${alts.look}</div>` : "";
  const lane = alts.prefLabel ? `<span class="gc-alts-lane">${alts.prefLabel}</span>` : "";
  return (
    `<div class="gc-alts">` +
    `<div class="gc-alts-top"><span class="gc-alts-h">Better options</span>${lane}</div>` +
    `${look}${rows}</div>`
  );
}

const WORDMARK = `<span class="gc-wordmark">good<i>_</i>clothes</span>`;

let _loadTimer = null;
let _loadStart = null;

function renderBadge(state) {
  const el = ensureBadge();
  const { materials, research, final, phase, alternatives } = state;

  if (phase === "loading") {
    if (_loadTimer) clearInterval(_loadTimer);
    _loadStart = Date.now();
    el.innerHTML =
      `<div class="gc-head">${WORDMARK}</div>` +
      `<div class="gc-hero">${ringSvg(null, 56, true)}` +
      `<div class="gc-hero-info"><div class="gc-verdict">Researching</div>` +
      `<div class="gc-brand">${state.brand || "…"}</div></div></div>` +
      `<div class="gc-loading">Researching brand… <span class="gc-eta" id="gc-eta">est. 15s</span></div>`;
    _loadTimer = setInterval(() => {
      const etaEl = document.getElementById("gc-eta");
      if (!etaEl) { clearInterval(_loadTimer); return; }
      const elapsed = Math.round((Date.now() - _loadStart) / 1000);
      const rem = Math.max(0, 15 - elapsed);
      etaEl.textContent = rem > 0 ? `est. ${rem}s remaining` : `still working… (${elapsed}s)`;
    }, 1000);
    return;
  }

  if (_loadTimer) { clearInterval(_loadTimer); _loadTimer = null; }

  const big = final != null ? final : materials && materials.score != null ? materials.score : null;
  const brand = state.brand || (research && research.brand) || "This item";

  // breakdown values
  const matVal = materials && materials.parsed ? materials.score : null;
  const matHint = "couldn't read fabric";
  let ethVal = null, ownVal = null, sources = "";
  if (phase === "partial") {
    // research unavailable
  } else if (research) {
    ethVal = research.ethics_score;
    ownVal = research.ownership_score;
    if (research.sources && research.sources.length) {
      sources =
        `<div class="gc-src"><span class="gc-src-h">Sources</span>` +
        research.sources
          .slice(0, 3)
          .map((s) => `<span class="gc-dot">·</span><a href="${s.url}" target="_blank">${s.label}</a>`)
          .join("") +
        `</div>`;
    }
  }

  const breakdown =
    `<div class="gc-divider"></div>` +
    metricRow("Materials", matVal, matHint) +
    metricRow("Ethics", ethVal, "research unavailable") +
    metricRow("Ownership", ownVal, "research unavailable");

  const summary =
    research && research.summary
      ? `<div class="gc-sum-wrap">` +
        `<div class="gc-sum">${research.summary}</div>` +
        `<span class="gc-readmore" onclick="var s=this.previousElementSibling;s.classList.toggle('gc-sum-open');this.textContent=s.classList.contains('gc-sum-open')?'Read less':'Read more'">Read more</span>` +
        `</div>`
      : "";

  const showAlts = final != null && final < ALT_THRESHOLD ? altsHtml(alternatives) : "";

  el.innerHTML =
    `<div class="gc-head">${WORDMARK}<div class="gc-actions"><button class="gc-replay" title="Re-score" id="gc-replay">↻</button><button class="gc-minimize" title="Minimize" id="gc-minimize">—</button></div></div>` +
    `<div class="gc-hero" id="gc-hero">${ringSvg(big, 56, big == null)}` +
    `<div class="gc-hero-info"><div class="gc-verdict">${verdictFor(big)}</div>` +
    `<div class="gc-brand">${brand}</div></div></div>` +
    `<div class="gc-collapsible">` + breakdown + summary + sources + showAlts + `</div>`;

  const replay = document.getElementById("gc-replay");
  if (replay) replay.addEventListener("click", startRun);

  const minimize = document.getElementById("gc-minimize");
  if (minimize) minimize.addEventListener("click", () => {
    el.classList.toggle("gc-min");
    minimize.textContent = el.classList.contains("gc-min") ? "+" : "—";
  });

  const hero = document.getElementById("gc-hero");
  if (hero) hero.addEventListener("click", () => {
    if (el.classList.contains("gc-min")) {
      el.classList.remove("gc-min");
      minimize.textContent = "—";
    }
  });
}

// ---------- 3. MAIN ---------- (unchanged logic)
function run(pref) {
  const data = scrape();
  const mat = window.GC_scoreMaterials(data.composition);
  renderBadge({ phase: "loading", materials: mat, brand: data.brand });

  chrome.runtime.sendMessage({ type: "RESEARCH", brand: data.brand }, (res) => {
    if (chrome.runtime.lastError || !res || res.error) {
      renderBadge({ phase: "partial", materials: mat, brand: data.brand });
      return;
    }
    const matScore = mat.score != null ? mat.score : 50;
    const final = Math.round(0.4 * matScore + 0.4 * res.ethics_score + 0.2 * res.ownership_score);
    chrome.storage.local.set({ gc_last: { materials: mat, research: res, final, brand: data.brand, url: data.url } });

    if (final >= ALT_THRESHOLD) {
      renderBadge({ phase: "done", materials: mat, research: res, final, brand: data.brand });
      return;
    }

    renderBadge({ phase: "done", materials: mat, research: res, final, brand: data.brand, alternatives: { loading: true } });
    chrome.runtime.sendMessage(
      { type: "ALTERNATIVES", brand: data.brand, title: data.title, score: final, composition: data.composition, image: data.image, pref },
      (alt) => {
        const alternatives = chrome.runtime.lastError || !alt || alt.error ? null : alt;
        if (alternatives) alternatives.prefLabel = window.GC_PREF_LABEL[pref] || "";
        renderBadge({ phase: "done", materials: mat, research: res, final, brand: data.brand, alternatives });
        if (alternatives) {
          chrome.storage.local.set({ gc_last: { materials: mat, research: res, final, brand: data.brand, alternatives, url: data.url } });
        }
      }
    );
  });
}

function startRun() {
  const old = document.getElementById("gc-badge");
  if (old) old.remove();
  if (_loadTimer) { clearInterval(_loadTimer); _loadTimer = null; }
  chrome.storage.sync.get({ gc_pref: window.GC_DEFAULT_PREF }, ({ gc_pref }) => run(gc_pref));
}

if (/\/product\//.test(location.pathname)) startRun();

chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === "GC_NAV") {
    setTimeout(startRun, 600);
  } else if (msg.type === "GC_NAV_AWAY") {
    const badge = document.getElementById("gc-badge");
    if (badge) badge.remove();
    if (_loadTimer) { clearInterval(_loadTimer); _loadTimer = null; }
  }
});

let _lastUrl = location.href;
setInterval(() => {
  if (location.href === _lastUrl) return;
  _lastUrl = location.href;
  if (/\/product\//.test(location.href)) {
    setTimeout(startRun, 600);
  } else {
    const badge = document.getElementById("gc-badge");
    if (badge) badge.remove();
  }
}, 500);
