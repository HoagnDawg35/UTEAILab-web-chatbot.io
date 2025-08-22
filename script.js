// ========== CONFIG ==========
const API_BASE_URL = "http://127.0.0.1:8000"; // Change to your backend

// ========== STATE ==========
let sessionId = null;

// ========== ELEMENTS ==========
const chatbotWindow = document.getElementById("chatbot-window");
const chatMessages = document.getElementById("chatbot-messages");
const chatbotToggle = document.getElementById("chatbot-toggle");
const closeChatBtn = document.getElementById("chatbot-close");
const refreshChatBtn = document.getElementById("refresh-chat");
const inputField = document.getElementById("chatbot-text");
const sendBtn = document.getElementById("chatbot-send");

// ========== INIT ==========
chatbotToggle.addEventListener("click", () => {
  chatbotWindow.style.display = "flex"; // always flex for chat layout
  chatbotToggle.style.display = "none";
});

closeChatBtn.addEventListener("click", () => {
  chatbotWindow.style.display = "none";
  chatbotToggle.style.display = "block";
});

refreshChatBtn.addEventListener("click", () => {
  chatMessages.innerHTML = "";
  localStorage.removeItem("chatbotSessionId"); // reset session completely
  sessionId = null;
  initSession();
});

sendBtn.addEventListener("click", sendMessage);
inputField.addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendMessage();
});

// On load → restore session or create new
initSession();

// ========== FUNCTIONS ==========
async function initSession() {
  sessionId = localStorage.getItem("chatbotSessionId");

  if (!sessionId) {
    try {
      const res = await fetch(`${API_BASE_URL}/api/new_session`);
      if (!res.ok) throw new Error("Failed to fetch new session");
      const data = await res.json();
      sessionId = data.session_id;
      localStorage.setItem("chatbotSessionId", sessionId);
      console.log("New Session ID:", sessionId);

      // Greet user on new session
      appendMessage("DengHuiHuang", "👋 Hello! How can I help you today?");
    } catch (error) {
      console.error("Failed to start session:", error);
      appendMessage("DengHuiHuang", "⚠️ Could not start chat session. Please refresh.");
      return;
    }
  }

  await loadHistory();
}

async function loadHistory() {
  try {
    const res = await fetch(`${API_BASE_URL}/api/history?session_id=${sessionId}`);
    if (!res.ok) throw new Error("Failed to load history");
    const data = await res.json();

    chatMessages.innerHTML = "";
    (data.messages || []).forEach((msg) =>
      appendMessage(msg.sender, msg.text)
    );

    // If history is empty → greet
    if (!data.messages || data.messages.length === 0) {
      appendMessage("DengHuiHuang", "👋 Hello! How can I help you today?");
    }
  } catch (error) {
    console.warn("No history available or failed to load:", error);
  }
}

async function sendMessage() {
  if (!sessionId) {
    appendMessage("DengHuiHuang", "⚠️ No session found. Please refresh.");
    return;
  }

  const userMessage = inputField.value.trim();
  if (!userMessage) return;

  appendMessage("You", userMessage);
  inputField.value = "";
  inputField.disabled = true;

  showTyping();

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message: userMessage }),
    });

    if (!response.ok) {
      hideTyping();
      appendMessage("AI", `⚠️ Server error (${response.status})`);
      return;
    }

    const data = await response.json();

    hideTyping();
    appendMessage("AI", data.reply);
  } catch (error) {
    hideTyping();
    appendMessage("AI", "⚠️ Network error. Please try again.");
    console.error("Fetch error:", error);
  } finally {
    inputField.disabled = false;
    inputField.focus();
  }
}

function appendMessage(sender, text) {
  const msgDiv = document.createElement("div");
  msgDiv.className = sender === "You" ? "chat-msg user" : "chat-msg ai";

  if (sender === "AI") {
    msgDiv.innerHTML = `<b>${sender}:</b><br>` + marked.parse(text);
  } else {
    msgDiv.innerHTML = `<b>${sender}:</b> ${text}`;
  }

  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: "smooth" });
}

function showTyping() {
  const typingDiv = document.createElement("div");
  typingDiv.id = "typing-indicator";
  typingDiv.classList.add("chat-msg", "ai");
  typingDiv.innerHTML = `
    <div class="typing">
      <span></span><span></span><span></span>
    </div>
  `;
  chatMessages.appendChild(typingDiv);
  chatMessages.scrollTo({ top: chatMessages.scrollHeight, behavior: "smooth" });
}

function hideTyping() {
  const typingDiv = document.getElementById("typing-indicator");
  if (typingDiv) typingDiv.remove();
}
