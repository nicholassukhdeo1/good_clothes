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

function scrape() {
  return {
    brand: findBrand(),
    composition: findComposition(),
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

function renderBadge(state) {
  const el = ensureBadge();
  const { materials, research, final, phase } = state;
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
    </div>`;
}

// ---------- 3. MAIN ----------
function run() {
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
    renderBadge({ phase: "done", materials: mat, research: res, final });
    chrome.storage.local.set({ gc_last: { materials: mat, research: res, final, url: data.url } });
  });
}

run();
