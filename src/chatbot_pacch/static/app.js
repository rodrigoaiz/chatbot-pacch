const form = document.querySelector("#chat-form");
const question = document.querySelector("#question");
const messages = document.querySelector("#messages");
const intro = document.querySelector("#intro");
const sources = document.querySelector("#sources");
const status = document.querySelector("#corpus-status");
const sendButton = form.querySelector("button[type='submit']");
const scopeLabel = document.querySelector("#scope-label");
let activeRequest = null;

function resizeComposer() {
  question.style.height = "auto";
  question.style.height = `${Math.min(question.scrollHeight, 160)}px`;
}

function addMessage(role, content = "") {
  const article = document.createElement("article");
  article.className = `message ${role}`;
  const label = document.createElement("div");
  label.className = "message-label";
  label.textContent = role === "user" ? "Tu pregunta" : "Explora CCH";
  const body = document.createElement("div");
  body.className = "message-body";
  body.textContent = content;
  article.append(label, body);
  messages.append(article);
  return { article, body };
}

function showThinking(body) {
  body.innerHTML = '<span class="thinking" aria-label="Buscando en los recursos"><i></i><i></i><i></i></span>';
}

function renderSources(items) {
  sources.replaceChildren();
  if (!items.length) {
    const empty = document.createElement("div");
    empty.className = "source-empty";
    empty.innerHTML = "<span>—</span><p>No se encontraron fuentes relacionadas.</p>";
    sources.append(empty);
    return;
  }
  items.forEach((item, index) => {
    const link = document.createElement("a");
    link.className = "source-card";
    link.href = item.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";

    const number = document.createElement("span");
    number.className = "source-card-number";
    number.textContent = String(index + 1).padStart(2, "0");
    const content = document.createElement("span");
    const title = document.createElement("strong");
    title.textContent = item.title;
    const meta = document.createElement("small");
    meta.textContent = item.heading === item.title ? item.subject : `${item.heading} · ${item.subject}`;
    content.append(title, meta);
    const arrow = document.createElement("span");
    arrow.className = "source-card-arrow";
    arrow.textContent = "↗";
    link.append(number, content, arrow);
    sources.append(link);
  });
}

async function ask(text) {
  const cleanText = text.trim();
  if (cleanText.length < 3 || activeRequest) return;

  intro.hidden = true;
  addMessage("user", cleanText);
  const assistant = addMessage("assistant");
  showThinking(assistant.body);
  question.value = "";
  resizeComposer();
  sendButton.disabled = true;
  activeRequest = new AbortController();
  messages.scrollIntoView({ behavior: "smooth", block: "end" });

  let responseText = "";
  try {
    const response = await fetch("api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: cleanText }),
      signal: activeRequest.signal,
    });
    if (!response.ok || !response.body) throw new Error("No se pudo iniciar la respuesta.");

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value || new Uint8Array(), { stream: !done });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      for (const line of lines) {
        if (!line.trim()) continue;
        const event = JSON.parse(line);
        if (event.type === "sources") renderSources(event.sources || []);
        if (event.type === "token") {
          responseText += event.content;
          assistant.body.textContent = responseText;
        }
        if (event.type === "error") throw new Error(event.message);
      }
      if (done) break;
    }
  } catch (error) {
    if (error.name !== "AbortError") {
      assistant.article.classList.add("error");
      assistant.body.textContent = error.message || "Ocurrió un error al generar la respuesta.";
    }
  } finally {
    activeRequest = null;
    sendButton.disabled = false;
    question.focus();
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  ask(question.value);
});

question.addEventListener("input", resizeComposer);
question.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    form.requestSubmit();
  }
});

document.querySelectorAll("[data-question]").forEach((button) => {
  button.addEventListener("click", () => ask(button.dataset.question));
});

fetch("api/corpus")
  .then((response) => response.json())
  .then((corpus) => {
    const ready = corpus.chunks > 0 && corpus.embedded_chunks === corpus.chunks;
    status.querySelector("span:last-child").textContent = ready
      ? `${corpus.documents} páginas · ${corpus.chunks} fragmentos listos`
      : `${corpus.documents} páginas · índice semántico incompleto`;
    status.classList.toggle("offline", !ready);
  })
  .catch(() => {
    status.querySelector("span:last-child").textContent = "Índice local no disponible";
    status.classList.add("offline");
  });

fetch("api/subjects")
  .then((response) => response.json())
  .then(({ subjects: indexedSubjects }) => {
    if (indexedSubjects.length === 1) {
      scopeLabel.textContent = `${indexedSubjects[0]} · piloto`;
    } else if (indexedSubjects.length > 1) {
      scopeLabel.textContent = `${indexedSubjects.length} materias indexadas · piloto`;
    }
  })
  .catch(() => {});
