// content.js
// Runs on the product page. Scrapes -> scores materials locally -> asks backend for
// brand research -> combines -> renders the badge.

// ---------- 1. SCRAPE (tuned for SSENSE) ----------
// Brand: SSENSE links the designer name to /<locale>/.../designers/<slug>, so the
// designer-link is a far stabler hook than the long Tailwind utility-class chain.
// Composition: SSENSE buries "100% cotton" inside a mixed "ITEM INFO" text block with
// no dedicated field, so instead of a brittle selector we scan for the leaf element
// whose text actually matches a fiber percentage (the trick that passed pre-flight).

// matches "100% cotton", "80% Cotton, 20% Polyester", "95% organic cotton", etc.
const FIBER_RE =
  /\b\d{1,3}\s*%\s*(?:organic |recycled |supima |pima )?(?:cotton|linen|hemp|wool|silk|cashmere|tencel|lyocell|modal|viscose|rayon|polyester|polyamide|nylon|elastane|spandex|acrylic|leather|cupro)/i;

function findBrand() {
  // primary: the designer link on the product page
  const designer = document.querySelector('a[href*="/designers/"]');
  if (designer && designer.innerText.trim()) return designer.innerText.trim();
  // fallbacks for layout/site variation
  const h1a = document.querySelector("h1 a");
  if (h1a && h1a.innerText.trim()) return h1a.innerText.trim();
  const h1 = document.querySelector("h1");
  if (h1 && h1.innerText.trim()) return h1.innerText.trim();
  return "Unknown";
}

function findComposition() {
  // Walk leaf elements and return the tightest text node that names a fiber %.
  // Tightest = avoids grabbing a giant parent block, but parseComposition() handles
  // either since it pulls every "\d+% fiber" out of whatever string it's given.
  let best = "";
  const els = document.querySelectorAll("li, p, span, div, td");
  for (const el of els) {
    if (el.children.length !== 0) continue; // leaf only
    const t = el.innerText && el.innerText.trim();
    if (t && FIBER_RE.test(t)) {
      if (!best || t.length < best.length) best = t;
    }
  }
  return best;
}

function findImage() {
  // og:image is the canonical product photo on virtually every retailer (incl. SSENSE),
  // and it's an absolute, publicly-fetchable URL — ideal to hand to Claude vision.
  const og = document.querySelector('meta[property="og:image"]');
  if (og && og.content) return og.content;
  // fallback: the largest <img> on the page is almost always the product shot
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

function colorFor(score) {
  if (score == null) return "#9aa0a6";
  if (score >= 70) return "#1e8e3e";
  if (score >= 45) return "#f9ab00";
  return "#d93025";
}

// Below this overall score, we nudge the shopper toward better options.
const ALT_THRESHOLD = 60;

function altsHtml(alts) {
  if (!alts) return "";
  if (alts.loading) return `<div class="gc-alts"><div class="gc-alts-h">Finding better options…</div></div>`;
  if (!alts.alternatives || !alts.alternatives.length) return "";
  const rows = alts.alternatives
    .map(
      (a) =>
        `<div class="gc-alt">` +
        `<a href="${a.url}" target="_blank" class="gc-alt-link">${a.name} <span class="gc-alt-shop">Shop ↗</span></a>` +
        `<span class="gc-alt-score">${a.est_score}</span>` +
        (a.why ? `<div class="gc-alt-why">${a.why}</div>` : "") +
        `</div>`
    )
    .join("");
  const look = alts.look
    ? `<div class="gc-alts-look">matching: ${alts.look}</div>`
    : "";
  const lane = alts.prefLabel ? ` · ${alts.prefLabel}` : "";
  return `<div class="gc-alts"><div class="gc-alts-h">⚠ Better ${alts.category || "options"}${lane}</div>${look}${rows}</div>`;
}

let _loadTimer = null;
let _loadStart = null;

function renderBadge(state) {
  const el = ensureBadge();
  const { materials, research, final, phase, alternatives } = state;

  if (phase === "loading") {
    if (_loadTimer) clearInterval(_loadTimer);
    _loadStart = Date.now();
    el.innerHTML = `
      <div class="gc-ring" style="--c:#9aa0a6">…</div>
      <div class="gc-body">
        <div class="gc-title">good_clothes</div>
        <div class="gc-row">Researching brand…</div>
        <div class="gc-row gc-eta" id="gc-eta">est. 15s</div>
      </div>`;
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

  const big = final != null ? final : materials && materials.score != null ? materials.score : "…";
  const ring = colorFor(typeof big === "number" ? big : null);

  const matLine =
    materials && materials.parsed
      ? `Materials ${materials.score}/100`
      : `Materials —  (couldn't read fabric)`;

  let ethLine = "Ethics …";
  let ownLine = "Ownership …";
  let sources = "";
  if (phase === "partial") {
    ethLine = "Ethics — (research unavailable)";
    ownLine = "";
  } else if (research) {
    ethLine = `Ethics ${research.ethics_score}/100`;
    ownLine = `Ownership ${research.ownership_score}/100`;
    if (research.sources && research.sources.length) {
      sources =
        `<div class="gc-src">` +
        research.sources
          .slice(0, 3)
          .map((s) => `<a href="${s.url}" target="_blank">${s.label}</a>`)
          .join(" · ") +
        `</div>`;
    }
  }

  el.innerHTML = `
    <div class="gc-ring" style="--c:${ring}">${big}</div>
    <div class="gc-body">
      <div class="gc-title">good_clothes</div>
      <div class="gc-row">${matLine}</div>
      <div class="gc-row">${ethLine}</div>
      ${ownLine ? `<div class="gc-row">${ownLine}</div>` : ""}
      ${research && research.summary ? `<div class="gc-sum">${research.summary}</div>` : ""}
      ${sources}
      ${altsHtml(alternatives)}
    </div>`;
}

// ---------- 3. MAIN ----------
function run(pref) {
  const data = scrape();
  const mat = window.GC_scoreMaterials(data.composition);
  renderBadge({ phase: "loading", materials: mat });

  chrome.runtime.sendMessage({ type: "RESEARCH", brand: data.brand }, (res) => {
    if (chrome.runtime.lastError || !res || res.error) {
      renderBadge({ phase: "partial", materials: mat });
      return;
    }
    const matScore = mat.score != null ? mat.score : 50; // fallback weight if fabric unreadable
    const final = Math.round(0.4 * matScore + 0.4 * res.ethics_score + 0.2 * res.ownership_score);
    chrome.storage.local.set({ gc_last: { materials: mat, research: res, final, url: data.url } });

    if (final >= ALT_THRESHOLD) {
      renderBadge({ phase: "done", materials: mat, research: res, final });
      return;
    }

    // Low score → this is the money shot: show better buys.
    renderBadge({ phase: "done", materials: mat, research: res, final, alternatives: { loading: true } });
    chrome.runtime.sendMessage(
      { type: "ALTERNATIVES", brand: data.brand, title: data.title, score: final, composition: data.composition, image: data.image, pref },
      (alt) => {
        const alternatives = chrome.runtime.lastError || !alt || alt.error ? null : alt;
        if (alternatives) alternatives.prefLabel = window.GC_PREF_LABEL[pref] || "";
        renderBadge({ phase: "done", materials: mat, research: res, final, alternatives });
        if (alternatives) {
          chrome.storage.local.set({ gc_last: { materials: mat, research: res, final, alternatives, url: data.url } });
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

// Initial load
startRun();

// SSENSE uses client-side routing (pushState), so the content script doesn't
// re-fire when the user clicks between products. Intercept history changes and
// re-run whenever the URL lands on a product page.
let _lastUrl = location.href;

function onNavigate() {
  const url = location.href;
  if (url === _lastUrl) return;
  _lastUrl = url;

  if (!/\/product\//.test(url)) {
    // navigated away from a product page — remove badge
    const badge = document.getElementById("gc-badge");
    if (badge) badge.remove();
    return;
  }

  // Give the SPA ~800ms to swap in the new product DOM before scraping
  setTimeout(startRun, 800);
}

const _origPush = history.pushState.bind(history);
history.pushState = function (...a) { _origPush(...a); onNavigate(); };

const _origReplace = history.replaceState.bind(history);
history.replaceState = function (...a) { _origReplace(...a); onNavigate(); };
