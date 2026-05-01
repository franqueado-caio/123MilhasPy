from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid
from user_agents import parse
from collections import deque
from threading import Timer, Lock
from typing import Dict, Optional, List, Any
import time

app = Flask(__name__)
CORS(app)


# =========================
# CONFIGURAÇÕES
# =========================
class Config:
    MAX_MENSAGENS_POR_SALA = 100
    MAX_FILA_ESPERA = 200
    TEMPO_LIMPEZA_INATIVOS = 300  # 5 minutos
    TEMPO_MAXIMO_INATIVIDADE = 1800  # 30 minutos
    TTL_CACHE_VERIFICACAO = 5  # segundos
    MAX_LOGS = 1000
    LIMITE_MENSAGEM_TAMANHO = 1000
    COOLDOWN_ENVIO = 1  # 1 segundo entre mensagens do mesmo usuário


# =========================
# TIMEZONE BRASIL
# =========================
tz_brasil = ZoneInfo("America/Sao_Paulo")


def agora() -> datetime:
    return datetime.now(tz_brasil)


def timestamp_str() -> str:
    return agora().strftime("%H:%M:%S")


def datetime_str() -> str:
    return agora().strftime("%Y-%m-%d %H:%M:%S")


# =========================
# ESTRUTURAS DE DADOS
# =========================
class FilaEspera:
    def __init__(self, maxlen: int = Config.MAX_FILA_ESPERA):
        self._fila = deque(maxlen=maxlen)
        self._lock = Lock()
        self._posicao_cache: Dict[str, int] = {}

    def adicionar(self, nome: str) -> Dict[str, Any]:
        with self._lock:
            for cliente in self._fila:
                if cliente["nome"] == nome:
                    return None
            cliente_id = str(uuid.uuid4())[:8]
            cliente = {
                "id": cliente_id,
                "nome": nome,
                "timestamp": timestamp_str(),
                "entrada_timestamp": time.time(),
            }
            self._fila.append(cliente)
            self._atualizar_cache_posicoes()
            return cliente

    def remover(self, cliente_id: str) -> Optional[Dict]:
        with self._lock:
            for i, cliente in enumerate(self._fila):
                if cliente["id"] == cliente_id:
                    removido = self._fila[i]
                    self._fila = deque(
                        [c for c in self._fila if c["id"] != cliente_id],
                        maxlen=self._fila.maxlen,
                    )
                    self._atualizar_cache_posicoes()
                    return removido
            return None

    def buscar(self, cliente_id: str) -> Optional[Dict]:
        with self._lock:
            for cliente in self._fila:
                if cliente["id"] == cliente_id:
                    return cliente
            return None

    def listar(self) -> List[Dict]:
        with self._lock:
            return [
                {
                    **cliente,
                    "posicao": idx + 1,
                    "tempo_espera": int(time.time() - cliente["entrada_timestamp"]),
                }
                for idx, cliente in enumerate(self._fila)
            ]

    def _atualizar_cache_posicoes(self):
        self._posicao_cache.clear()
        for idx, cliente in enumerate(self._fila):
            self._posicao_cache[cliente["id"]] = idx + 1

    def posicao(self, cliente_id: str) -> Optional[int]:
        return self._posicao_cache.get(cliente_id)

    def tamanho(self) -> int:
        return len(self._fila)

    def primeiro(self) -> Optional[Dict]:
        return self._fila[0] if self._fila else None


class GerenciadorSalas:
    def __init__(self):
        self._salas: Dict[str, Dict] = {}
        self._mensagens: Dict[str, deque] = {}
        self._cliente_para_sala: Dict[str, str] = {}
        self._lock = Lock()

    def criar_sala(self, cliente_id: str, operador: str) -> str:
        with self._lock:
            sala_id = f"sala_{cliente_id}_{int(time.time())}"
            self._salas[sala_id] = {
                "cliente_id": cliente_id,
                "operador": operador,
                "inicio_timestamp": time.time(),
                "inicio": timestamp_str(),
                "ultima_atividade": time.time(),
                "total_mensagens": 0,
                "ativa": True,
            }
            self._mensagens[sala_id] = deque(maxlen=Config.MAX_MENSAGENS_POR_SALA)
            self._cliente_para_sala[cliente_id] = sala_id
            return sala_id

    def obter_sala_por_cliente(self, cliente_id: str) -> Optional[str]:
        return self._cliente_para_sala.get(cliente_id)

    def obter_sala(self, sala_id: str) -> Optional[Dict]:
        return self._salas.get(sala_id)

    def adicionar_mensagem(self, sala_id: str, de: str, texto: str) -> Optional[Dict]:
        with self._lock:
            if sala_id not in self._salas:
                return None
            texto = texto.strip()[: Config.LIMITE_MENSAGEM_TAMANHO]
            if not texto:
                return None
            msg = {
                "de": de,
                "texto": texto,
                "timestamp": timestamp_str(),
                "time": time.time(),
            }
            self._mensagens[sala_id].append(msg)
            self._salas[sala_id]["ultima_atividade"] = time.time()
            self._salas[sala_id]["total_mensagens"] += 1
            return msg

    def obter_mensagens_novas(
        self, sala_id: str, ultimo_timestamp: float = 0
    ) -> List[Dict]:
        """Retorna APENAS mensagens com time > ultimo_timestamp"""
        if sala_id not in self._mensagens:
            return []
        return [
            msg
            for msg in self._mensagens[sala_id]
            if msg.get("time", 0) > ultimo_timestamp
        ]

    def fechar_sala(self, sala_id: str) -> bool:
        with self._lock:
            if sala_id not in self._salas:
                return False
            cliente_id = self._salas[sala_id]["cliente_id"]
            if cliente_id in self._cliente_para_sala:
                del self._cliente_para_sala[cliente_id]
            del self._salas[sala_id]
            if sala_id in self._mensagens:
                del self._mensagens[sala_id]
            return True

    def listar_salas_ativas(self) -> List[Dict]:
        with self._lock:
            salas_info = []
            for sala_id, sala in self._salas.items():
                tempo_inativo = int(time.time() - sala["ultima_atividade"])
                mensagens_sala = self._mensagens.get(sala_id, [])
                ultima_msg = mensagens_sala[-1] if mensagens_sala else None
                salas_info.append(
                    {
                        "sala_id": sala_id,
                        "cliente_id": sala["cliente_id"],
                        "operador": sala["operador"],
                        "inicio": sala["inicio"],
                        "ultima_atividade": (
                            timestamp_str()
                            if tempo_inativo < 60
                            else f"há {tempo_inativo//60}min"
                        ),
                        "tempo_inativo": tempo_inativo,
                        "total_mensagens": sala["total_mensagens"],
                        "ultima_mensagem": ultima_msg,
                    }
                )
            salas_info.sort(key=lambda x: x["tempo_inativo"])
            return salas_info

    def limpar_inativas(self):
        with self._lock:
            agora_ts = time.time()
            salas_remover = [
                sid
                for sid, sala in self._salas.items()
                if agora_ts - sala["ultima_atividade"] > Config.TEMPO_MAXIMO_INATIVIDADE
            ]
            for sala_id in salas_remover:
                self.fechar_sala(sala_id)
            return len(salas_remover)

    def estatisticas(self) -> Dict:
        total_mensagens = sum(len(msgs) for msgs in self._mensagens.values())
        return {
            "total_salas": len(self._salas),
            "total_mensagens": total_mensagens,
            "media_mensagens_por_sala": (
                total_mensagens / len(self._salas) if self._salas else 0
            ),
        }


class CacheRapido:
    def __init__(self, ttl: int = Config.TTL_CACHE_VERIFICACAO):
        self._cache: Dict[str, tuple] = {}
        self._ttl = ttl
        self._lock = Lock()

    def set(self, key: str, value: Any):
        with self._lock:
            self._cache[key] = (value, time.time())

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key not in self._cache:
                return None
            value, ts = self._cache[key]
            if time.time() - ts > self._ttl:
                del self._cache[key]
                return None
            return value

    def delete(self, key: str):
        with self._lock:
            if key in self._cache:
                del self._cache[key]

    def clear(self):
        with self._lock:
            self._cache.clear()


class CooldownManager:
    def __init__(self):
        self._cooldowns: Dict[str, float] = {}
        self._lock = Lock()

    def pode_enviar(self, cliente_id: str) -> bool:
        with self._lock:
            ultimo = self._cooldowns.get(cliente_id, 0)
            agora_ts = time.time()
            if agora_ts - ultimo >= Config.COOLDOWN_ENVIO:
                self._cooldowns[cliente_id] = agora_ts
                return True
            return False


# =========================
# INSTÂNCIAS GLOBAIS
# =========================
fila_espera = FilaEspera()
gerenciador = GerenciadorSalas()
cache_salas = CacheRapido(ttl=Config.TTL_CACHE_VERIFICACAO)
cooldown = CooldownManager()
logs = deque(maxlen=Config.MAX_LOGS)


# =========================
# LIMPEZA AUTOMÁTICA
# =========================
def limpeza_automatica():
    salas_removidas = gerenciador.limpar_inativas()
    cache_salas.clear()
    if salas_removidas > 0:
        print(f"🧹 Limpeza: {salas_removidas} sala(s) inativa(s) removidas")
    Timer(Config.TEMPO_LIMPEZA_INATIVOS, limpeza_automatica).start()


Timer(Config.TEMPO_LIMPEZA_INATIVOS, limpeza_automatica).start()


# =========================
# UTILITÁRIOS
# =========================
def detectar_dispositivo(req) -> Dict:
    ua_string = req.headers.get("User-Agent", "")
    ua = parse(ua_string)
    device_info = {
        "ip": req.headers.get("X-Forwarded-For", req.remote_addr),
        "browser": ua.browser.family,
        "os": ua.os.family,
        "is_mobile": ua.is_mobile,
        "device_type": "Mobile" if ua.is_mobile else "Desktop",
    }
    if "Android" in ua_string:
        device_info["os"] = "Android"
    elif "iPhone" in ua_string or "iPad" in ua_string:
        device_info["os"] = "iOS"
    return device_info


def registrar_log(rota: str, device_info: Dict):
    log = {
        "rota": rota,
        "ip": device_info["ip"],
        "os": device_info["os"],
        "device": device_info["device_type"],
        "browser": device_info["browser"],
        "timestamp": datetime_str(),
    }
    logs.append(log)


# =========================
# MIDDLEWARE
# =========================
@app.before_request
def before_request():
    if request.path.startswith(
        ("/static", "/api/mensagens", "/api/verificar_sala", "/api/status_cliente")
    ):
        return
    if request.path.startswith("/api/"):
        device_info = detectar_dispositivo(request)
        registrar_log(request.path, device_info)


# =========================
# ROTAS HTML
# =========================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/valet")
def valet():
    return render_template("valet.html")


@app.route("/habilitacao")
def habilitacao():
    return render_template("habilitacao.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/carteira")
def carteira():
    return render_template("carteira.html")


@app.route("/transferir")
def transferir():
    return render_template("transferir.html")


@app.route("/puxada_master")
def puxada_master():
    return render_template("puxada_master.html")


# =========================
# API CLIENTE
# =========================
@app.route("/api/entrar_fila", methods=["POST"])
def entrar_fila():
    data = request.json
    nome = data.get("nome", f"Cliente_{fila_espera.tamanho() + 1}")
    cliente = fila_espera.adicionar(nome)
    if not cliente:
        # Se já está na fila, retorna os dados existentes em vez de erro
        for c in fila_espera.listar():
            if c["nome"] == nome:
                return jsonify(
                    {
                        "success": True,
                        "cliente_id": c["id"],
                        "posicao": c["posicao"],
                        "message": f"Você já está na fila. Posição: {c['posicao']}",
                    }
                )
        return jsonify({"success": False, "message": "Você já está na fila"}), 400

    return jsonify(
        {
            "success": True,
            "cliente_id": cliente["id"],
            "posicao": fila_espera.tamanho(),
            "message": f"Você entrou na fila. Posição: {fila_espera.tamanho()}",
        }
    )


# ── ROTA QUE ESTAVA FALTANDO: /api/verificar_sala/<cliente_id> ──
@app.route("/api/verificar_sala/<cliente_id>", methods=["GET"])
def verificar_sala(cliente_id):
    """
    Usada pelo CLIENTE para verificar se já foi chamado para atendimento.
    Retorna sala_id se estiver em atendimento, ou status de fila se ainda aguardando.
    """
    # Cache primeiro
    sala_id_cache = cache_salas.get(cliente_id)
    if sala_id_cache:
        sala = gerenciador.obter_sala(sala_id_cache)
        if sala:
            return jsonify(
                {
                    "status": "em_atendimento",
                    "sala_id": sala_id_cache,
                    "operador": sala["operador"],
                }
            )

    # Verificar sala ativa
    sala_id = gerenciador.obter_sala_por_cliente(cliente_id)
    if sala_id:
        sala = gerenciador.obter_sala(sala_id)
        cache_salas.set(cliente_id, sala_id)
        return jsonify(
            {
                "status": "em_atendimento",
                "sala_id": sala_id,
                "operador": sala["operador"],
            }
        )

    # Verificar posição na fila
    posicao = fila_espera.posicao(cliente_id)
    if posicao:
        return jsonify(
            {
                "status": "aguardando",
                "posicao": posicao,
                "total_fila": fila_espera.tamanho(),
            }
        )

    return jsonify({"status": "nao_encontrado"}), 404


@app.route("/api/status_cliente/<cliente_id>", methods=["GET"])
def status_cliente(cliente_id):
    """Alias de verificar_sala para compatibilidade"""
    return verificar_sala(cliente_id)


@app.route("/api/enviar_mensagem", methods=["POST"])
def enviar_mensagem():
    data = request.json
    sala_id = data.get("sala_id")
    de = data.get("de")
    texto = data.get("texto")
    cliente_id = data.get("cliente_id")

    if not texto or not texto.strip():
        return jsonify({"success": False, "message": "Mensagem vazia"}), 400

    # Cooldown apenas para clientes
    if cliente_id and de != "operador" and de not in ["sistema"]:
        if not cooldown.pode_enviar(cliente_id):
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Aguarde antes de enviar outra mensagem",
                    }
                ),
                429,
            )

    msg = gerenciador.adicionar_mensagem(sala_id, de, texto)
    if not msg:
        return jsonify({"success": False, "message": "Sala não encontrada"}), 404

    return jsonify({"success": True, "mensagem": msg})


@app.route("/api/mensagens/<sala_id>", methods=["GET"])
def get_mensagens(sala_id):
    """
    Retorna SOMENTE mensagens novas após ultimo_timestamp.
    O cliente deve enviar o maior 'time' recebido anteriormente.
    """
    ultimo_timestamp = float(request.args.get("ultimo_timestamp", 0))
    novas = gerenciador.obter_mensagens_novas(sala_id, ultimo_timestamp)

    # Calcular novo timestamp = maior 'time' das mensagens retornadas
    novo_timestamp = max((m["time"] for m in novas), default=ultimo_timestamp)

    return jsonify(
        {
            "mensagens": novas,
            "total_novas": len(novas),
            "ultimo_timestamp": novo_timestamp,
        }
    )


# =========================
# API OPERADOR
# =========================
@app.route("/api/fila_espera", methods=["GET"])
def get_fila_espera():
    clientes = fila_espera.listar()
    return jsonify(
        {
            "clientes": clientes,
            "total": len(clientes),
            "tempo_medio_espera": calcular_tempo_medio_espera(clientes),
        }
    )


def calcular_tempo_medio_espera(clientes: List[Dict]) -> int:
    if not clientes:
        return 0
    total = sum(c.get("tempo_espera", 0) for c in clientes)
    return total // len(clientes)


@app.route("/api/salas_ativas", methods=["GET"])
def get_salas_ativas():
    salas = gerenciador.listar_salas_ativas()
    return jsonify(
        {
            "salas": salas,
            "total_salas": len(salas),
            "estatisticas": gerenciador.estatisticas(),
        }
    )


@app.route("/api/atender_cliente", methods=["POST"])
def atender_cliente():
    data = request.json
    cliente_id = data.get("cliente_id")
    operador = data.get("operador", "Operador")

    cliente = fila_espera.remover(cliente_id)
    if not cliente:
        return (
            jsonify({"success": False, "message": "Cliente não encontrado na fila"}),
            404,
        )

    sala_id = gerenciador.criar_sala(cliente_id, operador)

    # Mensagem de boas-vindas do sistema
    gerenciador.adicionar_mensagem(sala_id, "sistema", f"🔔 {operador} entrou no chat")

    return jsonify(
        {
            "success": True,
            "sala_id": sala_id,
            "cliente": {"nome": cliente["nome"], "id": cliente["id"]},
        }
    )


@app.route("/api/fechar_sala", methods=["POST"])
def fechar_sala():
    data = request.json
    sala_id = data.get("sala_id")

    # Adicionar mensagem de encerramento ANTES de fechar (cliente ainda pode buscar)
    gerenciador.adicionar_mensagem(
        sala_id, "sistema", "⚠️ O atendimento foi encerrado pelo operador."
    )

    # Pequeno delay para o cliente ter chance de buscar a mensagem
    # (na prática o cliente busca a cada 2s, então deixamos a sala por mais um ciclo)
    # Fechamento é feito logo após — em produção poderia usar um flag "encerrando"
    if gerenciador.fechar_sala(sala_id):
        return jsonify({"success": True, "message": "Sala fechada"})

    return jsonify({"success": False, "message": "Sala não encontrada"}), 404


@app.route("/api/estatisticas", methods=["GET"])
def estatisticas_gerais():
    salas_ativas = gerenciador.listar_salas_ativas()
    return jsonify(
        {
            "total_em_fila": fila_espera.tamanho(),
            "total_em_atendimento": len(salas_ativas),
            "logs_armazenados": len(logs),
            "estatisticas_salas": gerenciador.estatisticas(),
        }
    )


# =========================
# LOGS E MONITORAMENTO
# =========================
@app.route("/api/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", 100, type=int)
    logs_lista = list(logs)[-limit:]
    return jsonify(logs_lista[::-1])


@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "healthy",
            "timestamp": datetime_str(),
            "salas_ativas": len(gerenciador.listar_salas_ativas()),
            "fila_espera": fila_espera.tamanho(),
        }
    )


# =========================
# INICIALIZAÇÃO
# =========================
if __name__ == "__main__":
    print("🚀 Servidor iniciado:")
    print(f"   - Timezone: America/Sao_Paulo")
    print(f"   - Cooldown: {Config.COOLDOWN_ENVIO}s")
    print(f"   - Limpeza automática: a cada {Config.TEMPO_LIMPEZA_INATIVOS}s")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
