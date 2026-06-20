// content.js
// Runs on the product page. Scrapes -> scores materials locally -> asks backend for
// brand research -> combines -> renders the badge.

// ---------- 1. SCRAPE (TODO: set selectors for YOUR retailer) ----------
// Open a product page, inspect the brand + material-composition elements, paste
// their selectors here. THIS is the first thing to verify (see README pre-flight).
function scrape() {
  const brandEl = document.querySelector("TODO_BRAND_SELECTOR");
  const materialEl = document.querySelector("TODO_MATERIAL_SELECTOR");
  return {
    brand: (brandEl && brandEl.innerText.trim()) || "Unknown",
    composition: (materialEl && materialEl.innerText.trim()) || "",
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
