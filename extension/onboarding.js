// onboarding.js — populate the dropdown, restore the saved choice (cloud first, then
// local), and save back to both chrome.storage.sync AND the backend (Supabase).
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
sel.addEventListener("change", showHint);

const valid = (k) => window.GC_PREFS.some((p) => p.key === k);

// Restore: try the backend (so a reinstall on this machine recovers the choice),
// fall back to local chrome.storage, then the default.
window.GC_getUid((uid) => {
  chrome.storage.sync.get({ gc_pref: window.GC_DEFAULT_PREF }, ({ gc_pref }) => {
    fetch(`${window.GC_BACKEND}/prefs?user_id=${encodeURIComponent(uid)}`)
      .then((r) => r.json())
      .then((d) => {
        const pref = valid(d.pref) ? d.pref : gc_pref;
        sel.value = pref;
        showHint();
        if (valid(d.pref)) chrome.storage.sync.set({ gc_pref: d.pref });
      })
      .catch(() => {
        sel.value = gc_pref;
        showHint();
      });
  });
});

document.getElementById("save").addEventListener("click", () => {
  const pref = sel.value;
  chrome.storage.sync.set({ gc_pref: pref }); // instant local — never blocks on network
  window.GC_getUid((uid) => {
    fetch(`${window.GC_BACKEND}/prefs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid, pref }),
    })
      .then((r) => r.json())
      .then((d) => {
        saved.textContent = d.saved
          ? "Saved & synced to your account. You can close this tab."
          : "Saved on this device. You can close this tab.";
      })
      .catch(() => {
        saved.textContent = "Saved on this device. You can close this tab.";
      });
  });
});
