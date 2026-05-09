// static/js/chat-base.js
// ========== CHAT COMPLETO - FUNCIONAL ==========

const CHAT_CONFIG = {
  API: {
    ENTRAR_FILA: "/api/entrar_fila",
    VERIFICAR_SALA: "/api/verificar_sala",
    MENSAGENS: "/api/mensagens",
    ENVIAR: "/api/enviar_mensagem",
  },
  STORAGE_KEYS: {
    USER_NAME: "chatUserName",
  },
  POLLING: {
    VERIFICAR: 3000,
    MENSAGENS: 2000,
  },
};

let chatState = {
  clienteId: null,
  salaId: null,
  ultimoTimestamp: 0,
  nome: null,
  verifInterval: null,
  msgInterval: null,
};

function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function addChatMessage(tipo, texto, remetente = "") {
  const container = document.getElementById("chatMessages");
  if (!container) return;

  const div = document.createElement("div");
  div.className = `message-bubble ${tipo}`;

  let nome = "";
  if (tipo === "user") nome = "Você";
  else if (tipo === "operator") nome = remetente || "Atendente";
  else nome = "💬 Sistema";

  const hora = new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  div.innerHTML = `<strong>${nome}</strong><br>${escHtml(
    texto
  )}<span class="message-time">${hora}</span>`;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

async function entrarFila(nome) {
  try {
    const r = await fetch(CHAT_CONFIG.API.ENTRAR_FILA, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome }),
    });
    const d = await r.json();
    chatState.clienteId = d.cliente_id;
    chatState.nome = nome;
    addChatMessage(
      "system",
      `Olá ${nome}, você entrou na fila. Aguarde um atendente.`
    );

    if (chatState.verifInterval) clearInterval(chatState.verifInterval);
    chatState.verifInterval = setInterval(
      verificarSala,
      CHAT_CONFIG.POLLING.VERIFICAR
    );
  } catch {
    addChatMessage("system", "❌ Erro ao conectar. Tente novamente.");
  }
}

async function verificarSala() {
  if (chatState.salaId || !chatState.clienteId) return;

  try {
    const r = await fetch(
      `${CHAT_CONFIG.API.VERIFICAR_SALA}/${chatState.clienteId}`
    );
    const d = await r.json();

    if (d.status === "em_atendimento" && d.sala_id) {
      chatState.salaId = d.sala_id;
      clearInterval(chatState.verifInterval);
      chatState.verifInterval = null;
      addChatMessage(
        "operator",
        "🎧 Um atendente entrou no chat! Como posso ajudar?"
      );

      if (chatState.msgInterval) clearInterval(chatState.msgInterval);
      chatState.msgInterval = setInterval(
        buscarMensagens,
        CHAT_CONFIG.POLLING.MENSAGENS
      );
    }
  } catch {}
}

async function buscarMensagens() {
  if (!chatState.salaId) return;

  try {
    const r = await fetch(
      `${CHAT_CONFIG.API.MENSAGENS}/${chatState.salaId}?ultimo_timestamp=${chatState.ultimoTimestamp}`
    );
    const d = await r.json();

    if (d.mensagens && d.mensagens.length > 0) {
      d.mensagens.forEach((msg) => {
        if (msg.time > chatState.ultimoTimestamp)
          chatState.ultimoTimestamp = msg.time;
        if (msg.de === chatState.nome) return;

        if (msg.de === "sistema") {
          if (msg.texto && msg.texto.includes("encerrado")) {
            clearInterval(chatState.msgInterval);
            chatState.msgInterval = null;
            chatState.salaId = null;
          }
          addChatMessage("system", msg.texto);
        } else {
          addChatMessage("operator", msg.texto, msg.de);
        }
      });
      if (d.ultimo_timestamp > chatState.ultimoTimestamp)
        chatState.ultimoTimestamp = d.ultimo_timestamp;
    }
  } catch {}
}

async function enviarMensagem() {
  const input = document.getElementById("chatInput");
  const texto = input ? input.value.trim() : "";
  if (!texto) return;

  addChatMessage("user", texto);
  input.value = "";

  if (!chatState.salaId) return;

  try {
    const r = await fetch(CHAT_CONFIG.API.ENVIAR, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sala_id: chatState.salaId,
        de: chatState.nome,
        texto,
        cliente_id: chatState.clienteId,
      }),
    });
    const d = await r.json();
    if (
      d.success &&
      d.mensagem &&
      d.mensagem.time > chatState.ultimoTimestamp
    ) {
      chatState.ultimoTimestamp = d.mensagem.time;
    }
  } catch {}
}

function mostrarModalNome() {
  // Remove modal existente se houver
  const existingModal = document.getElementById("nomeModal");
  if (existingModal) existingModal.remove();

  const modalHtml = `
    <div id="nomeModal" style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.5);z-index:9999;display:flex;align-items:center;justify-content:center;">
      <div style="background:white;border-radius:20px;padding:25px;max-width:350px;width:90%;text-align:center;">
        <div style="margin-bottom:20px;">
          <img src="/static/assets/img/logo.avif" style="max-height:50px;" alt="Logo">
        </div>
        <h3 style="color:#f05929;margin-bottom:10px;">Bem-vindo!</h3>
        <p style="color:#6c757d;margin-bottom:20px;">Para começarmos, qual é o seu nome?</p>
        <input type="text" id="nomeInput" placeholder="Digite seu nome" style="width:100%;padding:12px;border:1px solid #e0e0e0;border-radius:10px;margin-bottom:20px;font-size:1rem;font-family:inherit;">
        <button id="confirmarNome" style="background:#f05929;color:white;border:none;padding:12px;border-radius:10px;cursor:pointer;width:100%;font-weight:700;">Começar atendimento</button>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML("beforeend", modalHtml);

  const inp = document.getElementById("nomeInput");
  if (inp) {
    inp.focus();
    inp.addEventListener("keypress", (e) => {
      if (e.key === "Enter") confirmarNome();
    });
  }
  const confirmBtn = document.getElementById("confirmarNome");
  if (confirmBtn) confirmBtn.onclick = confirmarNome;
}

function confirmarNome() {
  const nomeInput = document.getElementById("nomeInput");
  const nome = nomeInput ? nomeInput.value.trim() : "";
  if (!nome) {
    alert("Por favor, digite seu nome");
    return;
  }
  localStorage.setItem(CHAT_CONFIG.STORAGE_KEYS.USER_NAME, nome);
  const modal = document.getElementById("nomeModal");
  if (modal) modal.remove();
  entrarFila(nome);
}

// FUNÇÕES PÚBLICAS QUE O HTML ESPERA
window.abrirChat = async function () {
  const modal = document.getElementById("chatModal");
  if (modal) modal.classList.add("active");

  if (chatState.salaId || chatState.clienteId) return;

  const nome = localStorage.getItem(CHAT_CONFIG.STORAGE_KEYS.USER_NAME);
  if (!nome) {
    mostrarModalNome();
    return;
  }
  entrarFila(nome);
};

window.fecharChat = function () {
  const modal = document.getElementById("chatModal");
  if (modal) modal.classList.remove("active");
  if (chatState.msgInterval) clearInterval(chatState.msgInterval);
  if (chatState.verifInterval) clearInterval(chatState.verifInterval);
};

window.enviarMensagem = enviarMensagem;

// Configurar evento de enter no input do chat quando a página carregar
document.addEventListener("DOMContentLoaded", function () {
  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.addEventListener("keypress", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        enviarMensagem();
      }
    });
  }
});

console.log("✅ Chat base carregado com sucesso!");
