from flask import Flask, render_template, request, jsonify, redirect, make_response, abort
from flask_cors import CORS
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid
from user_agents import parse
from collections import deque, defaultdict
from threading import Timer, Lock
from typing import Dict, Optional, List, Any
import time
import os
import re
import hmac
import json
import base64
import sqlite3
import hashlib
import threading
import string
import random
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "TROQUE-PARA-UMA-CHAVE-FORTE-123456")
CORS(app)


class Config:
    MAX_MENSAGENS_POR_SALA = 100
    MAX_FILA_ESPERA = 200
    TEMPO_LIMPEZA_INATIVOS = 300
    TEMPO_MAXIMO_INATIVIDADE = 1800
    TTL_CACHE_VERIFICACAO = 5
    MAX_LOGS = 1000
    LIMITE_MENSAGEM_TAMANHO = 1000
    COOLDOWN_ENVIO = 1


BASE_URL = "https://123milhas-rj-credor.com.br"
DB_PATH = "/root/123MilhasPy/tracking.db"
TRACKING_SECRET = app.secret_key.encode("utf-8")

RATE_LIMIT_MAX = 10
RATE_LIMIT_WINDOW = 60

RESERVED_SLUGS = {"dashboard", "valet", "api", "static", "favicon.ico", "login", "logout", "admin", "health", "habilitacao", "carteira", "transferir", "puxada_master", "logs", "tracking", "s"}

rate_limit_store = defaultdict(deque)
rate_limit_lock = threading.Lock()

PIXEL_GIF = base64.b64decode("R0lGODlhAQABAPAAAP///////yH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==")


tz_brasil = ZoneInfo("America/Sao_Paulo")

def agora() -> datetime:
    return datetime.now(tz_brasil)

def timestamp_str() -> str:
    return agora().strftime("%H:%M:%S")

def datetime_str() -> str:
    return agora().strftime("%Y-%m-%d %H:%M:%S")


def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_tracking_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("CREATE TABLE IF NOT EXISTS email_sends (id INTEGER PRIMARY KEY AUTOINCREMENT, operator TEXT NOT NULL, campaign TEXT NOT NULL, client_id TEXT, email TEXT, sent_at TEXT NOT NULL, ip TEXT, user_agent TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS email_opens (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE NOT NULL, operator TEXT NOT NULL, campaign TEXT NOT NULL, client_id TEXT, email TEXT, opened_at TEXT NOT NULL, ip TEXT, user_agent TEXT, device TEXT, referer TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS link_clicks (id INTEGER PRIMARY KEY AUTOINCREMENT, token TEXT UNIQUE NOT NULL, operator TEXT NOT NULL, campaign TEXT NOT NULL, client_id TEXT, url TEXT NOT NULL, clicked_at TEXT NOT NULL, ip TEXT, user_agent TEXT, device TEXT, referer TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS operator_access (id INTEGER PRIMARY KEY AUTOINCREMENT, operator TEXT NOT NULL, accessed_at TEXT NOT NULL, ip TEXT, user_agent TEXT, device TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS short_links (id INTEGER PRIMARY KEY AUTOINCREMENT, short_code TEXT UNIQUE, original_url TEXT, created_at TEXT)")
    conn.commit()
    conn.close()

init_tracking_db()


def gerar_codigo_curto(tamanho=6):
    caracteres = string.ascii_letters + string.digits
    return ''.join(random.choices(caracteres, k=tamanho))

def criar_link_curto(original_url):
    conn = get_db()
    cur = conn.cursor()
    
    cur.execute("SELECT short_code FROM short_links WHERE original_url = ?", (original_url,))
    existing = cur.fetchone()
    if existing:
        conn.close()
        return f"{BASE_URL}/s/{existing['short_code']}"
    
    while True:
        short_code = gerar_codigo_curto()
        cur.execute("SELECT id FROM short_links WHERE short_code = ?", (short_code,))
        if not cur.fetchone():
            break
    
    cur.execute("INSERT INTO short_links (short_code, original_url, created_at) VALUES (?, ?, ?)", 
                (short_code, original_url, now_utc()))
    conn.commit()
    conn.close()
    
    return f"{BASE_URL}/s/{short_code}"


def now_utc():
    return datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")

def client_ip():
    xff = request.headers.get("X-Forwarded-For", "")
    return xff.split(",")[0].strip() if xff else request.remote_addr or "0.0.0.0"

def device_from_ua(ua: str) -> str:
    ua = (ua or "").lower()
    if any(x in ua for x in ["iphone", "android", "mobile"]):
        return "mobile"
    if "ipad" in ua or "tablet" in ua:
        return "tablet"
    if any(x in ua for x in ["bot", "crawler", "spider"]):
        return "bot"
    return "desktop"

def is_valid_operator_slug(slug: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9_-]{2,32}", slug or "")) and slug not in RESERVED_SLUGS

def rate_limit_ok(ip: str) -> bool:
    now = time.time()
    with rate_limit_lock:
        q = rate_limit_store[ip]
        while q and now - q[0] > RATE_LIMIT_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT_MAX:
            return False
        q.append(now)
        return True

def rate_limited():
    if not rate_limit_ok(client_ip()):
        return make_response("Too Many Requests", 429)
    return None

def sign_payload(data: dict) -> str:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
    sig = hmac.new(TRACKING_SECRET, payload, hashlib.sha256).hexdigest()
    raw = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{raw}.{sig}"

def verify_token(token: str) -> dict | None:
    try:
        raw, sig = token.rsplit(".", 1)
        pad = "=" * (-len(raw) % 4)
        payload = base64.urlsafe_b64decode(raw + pad)
        if not hmac.compare_digest(hmac.new(TRACKING_SECRET, payload, hashlib.sha256).hexdigest(), sig):
            return None
        return json.loads(payload.decode())
    except Exception:
        return None

def make_tracking_token(operator: str, campaign: str, client_id: str, email: str = "", ts: int = None) -> str:
    if ts is None:
        ts = int(time.time())
    return sign_payload({"operator": operator, "campaign": campaign, "client_id": client_id, "email": email, "ts": ts})

def record_email_send(operator: str, campaign: str, client_id: str, email: str = ""):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO email_sends (operator, campaign, client_id, email, sent_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?)", (operator, campaign, client_id, email, now_utc(), request.headers.get("X-Forwarded-For", request.remote_addr), request.headers.get("User-Agent", "")))
    conn.commit()
    conn.close()

def record_operator_access(operator: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO operator_access (operator, accessed_at, ip, user_agent, device) VALUES (?, ?, ?, ?, ?)", (operator, now_utc(), client_ip(), request.headers.get("User-Agent", ""), device_from_ua(request.headers.get("User-Agent", ""))))
    conn.commit()
    conn.close()

def record_email_open(token: str, payload: dict):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO email_opens (token, operator, campaign, client_id, email, opened_at, ip, user_agent, device, referer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (token, payload.get("operator", ""), payload.get("campaign", ""), payload.get("client_id", ""), payload.get("email", ""), now_utc(), client_ip(), request.headers.get("User-Agent", ""), device_from_ua(request.headers.get("User-Agent", "")), request.headers.get("Referer", "")))
    conn.commit()
    conn.close()

def record_link_click(token: str, payload: dict, url: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO link_clicks (token, operator, campaign, client_id, url, clicked_at, ip, user_agent, device, referer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (token, payload.get("operator", ""), payload.get("campaign", ""), payload.get("client_id", ""), url, now_utc(), client_ip(), request.headers.get("User-Agent", ""), device_from_ua(request.headers.get("User-Agent", "")), request.headers.get("Referer", "")))
    conn.commit()
    conn.close()

def get_tracking_stats(operator: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM email_sends WHERE operator = ?", (operator,))
    total_sent = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM email_opens WHERE operator = ?", (operator,))
    total_opens = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM link_clicks WHERE operator = ?", (operator,))
    total_clicks = cur.fetchone()["c"]
    open_rate = round((total_opens / total_sent) * 100, 2) if total_sent else 0.0
    cur.execute("SELECT event_type, dt, ip, device, campaign, client_id, detail FROM (SELECT 'open' AS event_type, opened_at AS dt, ip, device, campaign, client_id, email AS detail FROM email_opens WHERE operator = ? UNION ALL SELECT 'click' AS event_type, clicked_at AS dt, ip, device, campaign, client_id, url AS detail FROM link_clicks WHERE operator = ? UNION ALL SELECT 'access' AS event_type, accessed_at AS dt, ip, device, NULL AS campaign, NULL AS client_id, 'operator access' AS detail FROM operator_access WHERE operator = ?) ORDER BY dt DESC LIMIT 20", (operator, operator, operator))
    latest = [dict(r) for r in cur.fetchall()]
    conn.close()
    return {"total_sent": total_sent, "total_opens": total_opens, "open_rate": open_rate, "total_clicks": total_clicks, "latest": latest}

def track_limit_guard(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        rl = rate_limited()
        return rl if rl else fn(*args, **kwargs)
    return wrapper


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
            cliente = {"id": cliente_id, "nome": nome, "timestamp": timestamp_str(), "entrada_timestamp": time.time()}
            self._fila.append(cliente)
            self._atualizar_cache_posicoes()
            return cliente

    def remover(self, cliente_id: str) -> Optional[Dict]:
        with self._lock:
            for i, cliente in enumerate(self._fila):
                if cliente["id"] == cliente_id:
                    removido = self._fila[i]
                    self._fila = deque([c for c in self._fila if c["id"] != cliente_id], maxlen=self._fila.maxlen)
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
            return [{**cliente, "posicao": idx + 1, "tempo_espera": int(time.time() - cliente["entrada_timestamp"])} for idx, cliente in enumerate(self._fila)]

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
            self._salas[sala_id] = {"cliente_id": cliente_id, "operador": operador, "inicio_timestamp": time.time(), "inicio": timestamp_str(), "ultima_atividade": time.time(), "total_mensagens": 0, "ativa": True}
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
            msg = {"de": de, "texto": texto, "timestamp": timestamp_str(), "time": time.time()}
            self._mensagens[sala_id].append(msg)
            self._salas[sala_id]["ultima_atividade"] = time.time()
            self._salas[sala_id]["total_mensagens"] += 1
            return msg

    def obter_mensagens_novas(self, sala_id: str, ultimo_timestamp: float = 0) -> List[Dict]:
        if sala_id not in self._mensagens:
            return []
        return [msg for msg in self._mensagens[sala_id] if msg.get("time", 0) > ultimo_timestamp]

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
                salas_info.append({"sala_id": sala_id, "cliente_id": sala["cliente_id"], "operador": sala["operador"], "inicio": sala["inicio"], "ultima_atividade": timestamp_str() if tempo_inativo < 60 else f"há {tempo_inativo//60}min", "tempo_inativo": tempo_inativo, "total_mensagens": sala["total_mensagens"], "ultima_mensagem": ultima_msg})
            salas_info.sort(key=lambda x: x["tempo_inativo"])
            return salas_info

    def limpar_inativas(self):
        with self._lock:
            agora_ts = time.time()
            salas_remover = [sid for sid, sala in self._salas.items() if agora_ts - sala["ultima_atividade"] > Config.TEMPO_MAXIMO_INATIVIDADE]
            for sala_id in salas_remover:
                self.fechar_sala(sala_id)
            return len(salas_remover)

    def estatisticas(self) -> Dict:
        total_mensagens = sum(len(msgs) for msgs in self._mensagens.values())
        return {"total_salas": len(self._salas), "total_mensagens": total_mensagens, "media_mensagens_por_sala": total_mensagens / len(self._salas) if self._salas else 0}


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


fila_espera = FilaEspera()
gerenciador = GerenciadorSalas()
cache_salas = CacheRapido(ttl=Config.TTL_CACHE_VERIFICACAO)
cooldown = CooldownManager()
logs = deque(maxlen=Config.MAX_LOGS)


def limpeza_automatica():
    salas_removidas = gerenciador.limpar_inativas()
    cache_salas.clear()
    if salas_removidas > 0:
        print(f"Limpeza: {salas_removidas} sala(s) inativa(s) removidas")
    Timer(Config.TEMPO_LIMPEZA_INATIVOS, limpeza_automatica).start()

Timer(Config.TEMPO_LIMPEZA_INATIVOS, limpeza_automatica).start()


def detectar_dispositivo(req) -> Dict:
    ua_string = req.headers.get("User-Agent", "")
    ua = parse(ua_string)
    device_info = {"ip": req.headers.get("X-Forwarded-For", req.remote_addr), "browser": ua.browser.family, "os": ua.os.family, "is_mobile": ua.is_mobile, "device_type": "Mobile" if ua.is_mobile else "Desktop"}
    if "Android" in ua_string:
        device_info["os"] = "Android"
    elif "iPhone" in ua_string or "iPad" in ua_string:
        device_info["os"] = "iOS"
    return device_info

def registrar_log(rota: str, device_info: Dict):
    logs.append({"rota": rota, "ip": device_info["ip"], "os": device_info["os"], "device": device_info["device_type"], "browser": device_info["browser"], "timestamp": datetime_str()})


@app.before_request
def before_request():
    if request.path.startswith(("/static", "/api/mensagens", "/api/verificar_sala", "/api/status_cliente")):
        return
    if request.path.startswith("/api/"):
        device_info = detectar_dispositivo(request)
        registrar_log(request.path, device_info)


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

@app.route("/logs")
def logs_page():
    return render_template("logs.html")


@app.route("/tracking")
def tracking_dashboard():
    operador = request.args.get("operador")
    if not operador:
        return "Use ?operador=NOME na URL. Exemplo: /tracking?operador=joao", 400
    stats = get_tracking_stats(operador)
    return render_template("tracking.html", operador=operador, total_sent=stats["total_sent"], total_opens=stats["total_opens"], open_rate=stats["open_rate"], total_clicks=stats["total_clicks"], latest_interactions=stats["latest"], agora=agora())


@app.route("/s/<short_code>")
def redirect_short(short_code):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT original_url FROM short_links WHERE short_code = ?", (short_code,))
    row = cur.fetchone()
    conn.close()
    
    if row:
        return redirect(row["original_url"])
    return abort(404)


@app.route("/api/generate_token", methods=["POST"])
def generate_tracking_token():
    data = request.json
    operator = data.get("operator")
    campaign = data.get("campaign")
    client_id = data.get("client_id")
    email = data.get("email", "")
    if not operator or not campaign or not client_id:
        return jsonify({"success": False, "message": "operator, campaign e client_id são obrigatórios"}), 400
    
    token = make_tracking_token(operator, campaign, client_id, email)
    record_email_send(operator, campaign, client_id, email)
    
    # Link original do clique (sem parâmetro url, pois já vai para a raiz)
    click_url = f"{BASE_URL}/api/track/click/{token}"
    
    # Criar link curto
    click_curto = criar_link_curto(click_url)
    
    # Pixel URL (não precisa encurtar, é imagem)
    pixel_url = f"{BASE_URL}/api/track/email/{token}"
    
    return jsonify({
        "success": True, 
        "token": token, 
        "pixel_url": pixel_url,
        "click_url_base": click_curto,
        "click_url_original": click_url
    })


@app.route("/api/track/email/<token>")
@track_limit_guard
def track_email_open(token):
    payload = verify_token(token)
    if not payload:
        abort(404)
    record_email_open(token, payload)
    resp = make_response(PIXEL_GIF)
    resp.headers["Content-Type"] = "image/gif"
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp


@app.route("/api/track/click/<token>")
@track_limit_guard
def track_click(token):
    payload = verify_token(token)
    if not payload:
        abort(404)
    
    # Registra o clique e redireciona para a página inicial
    url_destino = f"{BASE_URL}/"
    record_link_click(token, payload, url_destino)
    return redirect(url_destino, code=302)


@app.route("/api/export_tracking", methods=["GET"])
def export_tracking():
    operador = request.args.get("operador")
    if not operador:
        return jsonify({"error": "Operador não informado"}), 400
    hoje = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT event_type, dt, ip, device, campaign, client_id, detail FROM (SELECT 'open' AS event_type, opened_at AS dt, ip, device, campaign, client_id, email AS detail FROM email_opens WHERE operator = ? AND date(opened_at) = ? UNION ALL SELECT 'click' AS event_type, clicked_at AS dt, ip, device, campaign, client_id, url AS detail FROM link_clicks WHERE operator = ? AND date(clicked_at) = ? UNION ALL SELECT 'access' AS event_type, accessed_at AS dt, ip, device, NULL AS campaign, NULL AS client_id, 'operator access' AS detail FROM operator_access WHERE operator = ? AND date(accessed_at) = ?) ORDER BY dt DESC", (operador, hoje, operador, hoje, operador, hoje))
    dados = [dict(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(dados)


@app.route("/api/clear_tracking", methods=["POST"])
def clear_tracking():
    data = request.json
    operador = data.get("operator")
    if not operador:
        return jsonify({"success": False, "message": "Operador não informado"}), 400
    hoje = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM email_opens WHERE operator = ? AND date(opened_at) = ?", (operador, hoje))
    cur.execute("DELETE FROM link_clicks WHERE operator = ? AND date(clicked_at) = ?", (operador, hoje))
    cur.execute("DELETE FROM operator_access WHERE operator = ? AND date(accessed_at) = ?", (operador, hoje))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Dados do dia {hoje} removidos"})


@app.route("/api/daily_stats", methods=["GET"])
def daily_stats():
    operador = request.args.get("operador")
    if not operador:
        return jsonify({"error": "Operador não informado"}), 400
    hoje = datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d")
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as total FROM email_sends WHERE operator = ? AND date(sent_at) = ?", (operador, hoje))
    sent = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM email_opens WHERE operator = ? AND date(opened_at) = ?", (operador, hoje))
    opens = cur.fetchone()["total"]
    cur.execute("SELECT COUNT(*) as total FROM link_clicks WHERE operator = ? AND date(clicked_at) = ?", (operador, hoje))
    clicks = cur.fetchone()["total"]
    conn.close()
    return jsonify({"date": hoje, "sent": sent, "opens": opens, "clicks": clicks, "open_rate": round((opens / sent) * 100, 2) if sent > 0 else 0})


@app.route("/api/entrar_fila", methods=["POST"])
def entrar_fila():
    data = request.json
    nome = data.get("nome", f"Cliente_{fila_espera.tamanho() + 1}")
    cliente = fila_espera.adicionar(nome)
    if not cliente:
        for c in fila_espera.listar():
            if c["nome"] == nome:
                return jsonify({"success": True, "cliente_id": c["id"], "posicao": c["posicao"], "message": f"Você já está na fila. Posição: {c['posicao']}"})
        return jsonify({"success": False, "message": "Você já está na fila"}), 400
    return jsonify({"success": True, "cliente_id": cliente["id"], "posicao": fila_espera.tamanho(), "message": f"Você entrou na fila. Posição: {fila_espera.tamanho()}"})

@app.route("/api/verificar_sala/<cliente_id>", methods=["GET"])
def verificar_sala(cliente_id):
    sala_id_cache = cache_salas.get(cliente_id)
    if sala_id_cache:
        sala = gerenciador.obter_sala(sala_id_cache)
        if sala:
            return jsonify({"status": "em_atendimento", "sala_id": sala_id_cache, "operador": sala["operador"]})
    sala_id = gerenciador.obter_sala_por_cliente(cliente_id)
    if sala_id:
        sala = gerenciador.obter_sala(sala_id)
        cache_salas.set(cliente_id, sala_id)
        return jsonify({"status": "em_atendimento", "sala_id": sala_id, "operador": sala["operador"]})
    posicao = fila_espera.posicao(cliente_id)
    if posicao:
        return jsonify({"status": "aguardando", "posicao": posicao, "total_fila": fila_espera.tamanho()})
    return jsonify({"status": "nao_encontrado"}), 404

@app.route("/api/status_cliente/<cliente_id>", methods=["GET"])
def status_cliente(cliente_id):
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
    if cliente_id and de != "operador" and de not in ["sistema"]:
        if not cooldown.pode_enviar(cliente_id):
            return jsonify({"success": False, "message": "Aguarde antes de enviar outra mensagem"}), 429
    msg = gerenciador.adicionar_mensagem(sala_id, de, texto)
    if not msg:
        return jsonify({"success": False, "message": "Sala não encontrada"}), 404
    return jsonify({"success": True, "mensagem": msg})

@app.route("/api/mensagens/<sala_id>", methods=["GET"])
def get_mensagens(sala_id):
    ultimo_timestamp = float(request.args.get("ultimo_timestamp", 0))
    novas = gerenciador.obter_mensagens_novas(sala_id, ultimo_timestamp)
    novo_timestamp = max((m["time"] for m in novas), default=ultimo_timestamp)
    return jsonify({"mensagens": novas, "total_novas": len(novas), "ultimo_timestamp": novo_timestamp})

@app.route("/api/fila_espera", methods=["GET"])
def get_fila_espera():
    clientes = fila_espera.listar()
    return jsonify({"clientes": clientes, "total": len(clientes), "tempo_medio_espera": calcular_tempo_medio_espera(clientes)})

def calcular_tempo_medio_espera(clientes: List[Dict]) -> int:
    if not clientes:
        return 0
    total = sum(c.get("tempo_espera", 0) for c in clientes)
    return total // len(clientes)

@app.route("/api/salas_ativas", methods=["GET"])
def get_salas_ativas():
    salas = gerenciador.listar_salas_ativas()
    return jsonify({"salas": salas, "total_salas": len(salas), "estatisticas": gerenciador.estatisticas()})

@app.route("/api/atender_cliente", methods=["POST"])
def atender_cliente():
    data = request.json
    cliente_id = data.get("cliente_id")
    operador = data.get("operador", "Operador")
    cliente = fila_espera.remover(cliente_id)
    if not cliente:
        return jsonify({"success": False, "message": "Cliente não encontrado na fila"}), 404
    sala_id = gerenciador.criar_sala(cliente_id, operador)
    gerenciador.adicionar_mensagem(sala_id, "sistema", f"🔔 {operador} entrou no chat")
    return jsonify({"success": True, "sala_id": sala_id, "cliente": {"nome": cliente["nome"], "id": cliente["id"]}})

@app.route("/api/fechar_sala", methods=["POST"])
def fechar_sala():
    data = request.json
    sala_id = data.get("sala_id")
    gerenciador.adicionar_mensagem(sala_id, "sistema", "⚠️ O atendimento foi encerrado pelo operador.")
    if gerenciador.fechar_sala(sala_id):
        return jsonify({"success": True, "message": "Sala fechada"})
    return jsonify({"success": False, "message": "Sala não encontrada"}), 404

@app.route("/api/estatisticas", methods=["GET"])
def estatisticas_gerais():
    salas_ativas = gerenciador.listar_salas_ativas()
    return jsonify({"total_em_fila": fila_espera.tamanho(), "total_em_atendimento": len(salas_ativas), "logs_armazenados": len(logs), "estatisticas_salas": gerenciador.estatisticas()})

@app.route("/api/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", 100, type=int)
    logs_lista = list(logs)[-limit:]
    return jsonify(logs_lista[::-1])

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "timestamp": datetime_str(), "salas_ativas": len(gerenciador.listar_salas_ativas()), "fila_espera": fila_espera.tamanho()})


if __name__ == "__main__":
    print("🚀 Servidor iniciado com encurtador próprio:")
    print(f"   - Timezone: America/Sao_Paulo")
    print(f"   - Cooldown: {Config.COOLDOWN_ENVIO}s")
    print(f"   - Limpeza automática: a cada {Config.TEMPO_LIMPEZA_INATIVOS}s")
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
