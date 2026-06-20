// onboarding.js — populate the dropdown from prefs.js, load any saved choice, save back.
const sel = document.getElementById("pref");
const hint = document.getElementById("hint");
const saved = document.getElementById("saved");

for (const p of window.GC_PREFS) {
  const opt = document.createElement("option");
  opt.value = p.key;
  opt.textContent = p.label;
  sel.appendChild(opt);
}

function showHint() {
  const p = window.GC_PREFS.find((x) => x.key === sel.value);
  hint.textContent = p ? p.hint : "";
}

// Pre-select the saved value (so re-opening from the popup reflects current choice).
chrome.storage.sync.get({ gc_pref: window.GC_DEFAULT_PREF }, ({ gc_pref }) => {
  sel.value = gc_pref;
  showHint();
});

sel.addEventListener("change", showHint);

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.sync.set({ gc_pref: sel.value }, () => {
    saved.textContent = "Saved — you're all set. You can close this tab.";
  });
});
