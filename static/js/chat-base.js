// static/js/chat-base.js - VERSÃO IDÊNTICA AO QUE FUNCIONA
// ========== CHAT COMPLETO - USANDO /api/chat/ ==========

const STORAGE_KEYS = {
  CREDOR_DATA: "credorData",
  USER_NAME: "chatUserName",
};

let chatClienteId = null;
let chatSalaId = null;
let chatUltimoTs = 0;
let chatNome = null;
let chatVerifInterval = null;
let chatMsgInterval = null;

function escHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function addMsg(tipo, texto, remetente) {
  const c = document.getElementById("chatMessages");
  if (!c) return;
  const div = document.createElement("div");
  div.className = `message-bubble ${tipo}`;
  const nome =
    tipo === "user"
      ? "Você"
      : tipo === "operator"
      ? remetente || "Atendente"
      : "💬 Sistema";
  const hora = new Date().toLocaleTimeString("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
  });
  div.innerHTML = `<strong>${nome}</strong><br>${escHtml(
    texto
  )}<span class="message-time">${hora}</span>`;
  c.appendChild(div);
  c.scrollTop = c.scrollHeight;
}

async function entrarFila(nome) {
  try {
    const r = await fetch("/api/chat/entrar_fila", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome }),
    });
    const d = await r.json();
    chatClienteId = d.cliente_id;
    chatNome = nome;
    addMsg("system", `Olá ${nome}, você entrou na fila. Aguarde um atendente.`);
    if (chatVerifInterval) clearInterval(chatVerifInterval);
    chatVerifInterval = setInterval(verificarSala, 3000);
  } catch {
    addMsg("system", "❌ Erro ao conectar. Tente novamente.");
  }
}

async function verificarSala() {
  if (chatSalaId || !chatClienteId) return;
  try {
    const r = await fetch(`/api/chat/verificar_sala/${chatClienteId}`);
    const d = await r.json();
    if (d.status === "em_atendimento" && d.sala_id) {
      chatSalaId = d.sala_id;
      clearInterval(chatVerifInterval);
      chatVerifInterval = null;
      addMsg("operator", "🎧 Um atendente entrou no chat! Como posso ajudar?");
      if (chatMsgInterval) clearInterval(chatMsgInterval);
      chatMsgInterval = setInterval(buscarMensagens, 2000);
    }
  } catch {}
}

async function buscarMensagens() {
  if (!chatSalaId) return;
  try {
    const r = await fetch(
      `/api/chat/mensagens/${chatSalaId}?ultimo_timestamp=${chatUltimoTs}`
    );
    const d = await r.json();
    if (d.mensagens && d.mensagens.length > 0) {
      d.mensagens.forEach((msg) => {
        if (msg.time > chatUltimoTs) chatUltimoTs = msg.time;
        if (msg.de === chatNome) return;
        if (msg.de === "sistema") {
          if (msg.texto && msg.texto.includes("encerrado")) {
            clearInterval(chatMsgInterval);
            chatMsgInterval = null;
            chatSalaId = null;
          }
          addMsg("system", msg.texto);
        } else {
          addMsg("operator", msg.texto, msg.de);
        }
      });
      if (d.ultimo_timestamp > chatUltimoTs) chatUltimoTs = d.ultimo_timestamp;
    }
  } catch {}
}

async function enviarMensagem() {
  const input = document.getElementById("chatInput");
  const texto = input ? input.value.trim() : "";
  if (!texto) return;
  addMsg("user", texto);
  input.value = "";
  if (!chatSalaId) return;
  try {
    const r = await fetch("/api/chat/enviar_mensagem", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sala_id: chatSalaId,
        de: chatNome,
        texto,
        cliente_id: chatClienteId,
      }),
    });
    const d = await r.json();
    if (d.success && d.mensagem && d.mensagem.time > chatUltimoTs)
      chatUltimoTs = d.mensagem.time;
  } catch {}
}

function pedirNome() {
  // Fechar modal existente
  const existingModal = document.getElementById("modalAtivo");
  if (existingModal) existingModal.remove();

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";
  overlay.id = "modalAtivo";
  overlay.innerHTML = `
    <div class="modal-box">
      <div class="modal-logo-wrap">
        <img src="/static/assets/img/logo.avif" alt="123 Milhas" />
      </div>
      <h3>Bem-vindo!</h3>
      <p>Para iniciarmos o atendimento, qual é o seu nome?</p>
      <input type="text" id="nomeInputModal" placeholder="Digite seu nome" style="width:100%;padding:0.85rem 1rem;border:1.5px solid #e0e0e0;border-radius:14px;font-size:0.95rem;font-family:inherit;margin-bottom:1rem;outline:none;transition:border-color 0.2s;" onfocus="this.style.borderColor='#f05929'" onblur="this.style.borderColor='#e0e0e0'" />
      <button class="modal-btn primary" id="btnConfNome">Começar atendimento</button>
    </div>`;
  document.body.appendChild(overlay);
  const inp = document.getElementById("nomeInputModal");
  inp.focus();
  inp.addEventListener("keypress", (e) => {
    if (e.key === "Enter") confirmarNome();
  });
  document.getElementById("btnConfNome").onclick = confirmarNome;
}

function confirmarNome() {
  const nome = (document.getElementById("nomeInputModal")?.value || "").trim();
  if (!nome) {
    alert("Por favor, digite seu nome para iniciar o atendimento.");
    return;
  }
  localStorage.setItem(STORAGE_KEYS.USER_NAME, nome);
  const modal = document.getElementById("modalAtivo");
  if (modal) modal.remove();
  entrarFila(nome);
}

// Funções EXPORTADAS para o escopo global (o HTML espera essas)
window.abrirChat = async function () {
  const modal = document.getElementById("chatModal");
  if (modal) modal.classList.add("active");
  if (chatSalaId || chatClienteId) return;
  const nome = localStorage.getItem(STORAGE_KEYS.USER_NAME);
  if (!nome) {
    pedirNome();
    return;
  }
  entrarFila(nome);
};

window.fecharChat = function () {
  const modal = document.getElementById("chatModal");
  if (modal) modal.classList.remove("active");
};

window.enviarMensagem = enviarMensagem;

// Configurar evento de enter no input do chat quando a página carregar
document.addEventListener("DOMContentLoaded", function () {
  const chatInput = document.getElementById("chatInput");
  if (chatInput) {
    chatInput.addEventListener("keypress", (e) => {
      if (e.key === "Enter") enviarMensagem();
    });
  }
});

console.log("✅ Chat base carregado com sucesso!");
