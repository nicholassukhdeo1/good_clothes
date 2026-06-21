// onboarding.js — chat-based style onboarding.
// Sends conversation history to /chat, gets back a {message, pref_text} response.
// When the user is happy, saves pref_text to chrome.storage.sync + Supabase.

const chatWrap  = document.getElementById("chat-wrap");
const msgInput  = document.getElementById("msg-input");
const sendBtn   = document.getElementById("send-btn");
const briefWrap = document.getElementById("brief-wrap");
const briefText = document.getElementById("brief-text");
const saveBtn   = document.getElementById("save-btn");
const savedMsg  = document.getElementById("saved-msg");

// Full conversation history in the format the /chat API expects.
// We store assistant messages as raw JSON strings (what Claude returned).
const history = [];
let currentPrefText = "";

const OPENING = "Hey! I'm here to learn your style so good_clothes can suggest alternatives you'd actually want to wear. What's your aesthetic — designer, streetwear, minimal, grungy, something else?";

function addBubble(role, text, isTyping = false) {
  const row = document.createElement("div");
  row.className = `bubble-row ${role}`;
  const bubble = document.createElement("div");
  bubble.className = `bubble${isTyping ? " typing" : ""}`;
  bubble.textContent = text;
  row.appendChild(bubble);
  chatWrap.appendChild(row);
  chatWrap.scrollTop = chatWrap.scrollHeight;
  return bubble;
}

function setPrefText(text) {
  if (!text) return;
  currentPrefText = text;
  briefText.textContent = text;
  briefWrap.classList.add("visible");
  saveBtn.classList.add("ready");
}

async function sendMessage(userText) {
  sendBtn.disabled = true;
  msgInput.disabled = true;

  addBubble("user", userText);
  history.push({ role: "user", content: userText });

  const typingBubble = addBubble("assistant", "Thinking…", true);

  try {
    const resp = await fetch(`${window.GC_BACKEND}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages: history }),
    });
    const data = await resp.json();

    const msg = data.message || "Tell me more about your style.";
    typingBubble.textContent = msg;
    typingBubble.classList.remove("typing");

    // Store the raw JSON string as the assistant turn so Claude sees its own format.
    history.push({ role: "assistant", content: JSON.stringify(data) });

    if (data.pref_text) setPrefText(data.pref_text);
  } catch {
    typingBubble.textContent = "Something went wrong — try again.";
    typingBubble.classList.remove("typing");
    history.pop(); // remove the user turn so they can retry
  }

  sendBtn.disabled = false;
  msgInput.disabled = false;
  msgInput.focus();
}

function handleSend() {
  const text = msgInput.value.trim();
  if (!text) return;
  msgInput.value = "";
  sendMessage(text);
}

sendBtn.addEventListener("click", handleSend);
msgInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
});

saveBtn.addEventListener("click", () => {
  if (!currentPrefText) return;
  const pref = currentPrefText;
  chrome.storage.sync.set({ gc_pref: pref });
  window.GC_getUid((uid) => {
    fetch(`${window.GC_BACKEND}/prefs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: uid, pref }),
    })
      .then((r) => r.json())
      .then((d) => {
        savedMsg.textContent = d.saved
          ? "Saved & synced. You can close this tab."
          : "Saved on this device. You can close this tab.";
      })
      .catch(() => {
        savedMsg.textContent = "Saved on this device. You can close this tab.";
      });
  });
});

// Show the opening message immediately — no API call needed.
addBubble("assistant", OPENING);
// Seed history so Claude knows what it already said.
history.push({ role: "assistant", content: JSON.stringify({ message: OPENING, pref_text: "" }) });

// Restore existing pref if the user already has one.
window.GC_getUid((uid) => {
  chrome.storage.sync.get({ gc_pref: "" }, ({ gc_pref }) => {
    if (gc_pref) setPrefText(gc_pref);
  });
});

msgInput.focus();
