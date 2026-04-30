from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime
from zoneinfo import ZoneInfo
import uuid
from user_agents import parse

app = Flask(__name__)
CORS(app)

# =========================
# TIMEZONE PADRÃO BRASIL
# =========================
def agora():
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

# =========================
# DADOS EM MEMÓRIA
# =========================
fila_espera = []
salas_ativas = {}
mensagens = []
logs = []

# =========================
# DETECÇÃO DE DISPOSITIVO
# =========================
def detectar_dispositivo(req):
    ua_string = req.headers.get("User-Agent", "")
    ua = parse(ua_string)

    if "Android" in ua_string:
        os = "Android"
    elif "iPhone" in ua_string or "iPad" in ua_string:
        os = "iOS"
    else:
        os = ua.os.family

    device = "Mobile" if ua.is_mobile else "Desktop"
    browser = ua.browser.family
    ip = req.headers.get("X-Forwarded-For", req.remote_addr)

    return {
        "ip": ip,
        "os": os,
        "device": device,
        "browser": browser,
    }

# =========================
# TRACK GLOBAL
# =========================
@app.before_request
def track_request():
    if request.path.startswith("/logs"):
        return

    info = detectar_dispositivo(request)

    log = {
        "rota": request.path,
        "ip": info["ip"],
        "os": info["os"],
        "device": info["device"],
        "browser": info["browser"],
        "timestamp": agora().strftime("%Y-%m-%d %H:%M:%S"),
    }

    logs.append(log)

    if len(logs) > 500:
        logs.pop(0)

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

@app.route("/carteira.html")
def carteira_html():
    return render_template("carteira.html")

@app.route("/puxada_master")
def puxada_master_html():
    return render_template("puxada_master.html")

@app.route("/transferir")
def transferir():
    return render_template("transferir.html")

@app.route("/home")
def home():
    return render_template("home.html")

@app.route("/operador-email")
def operador_email():
    return render_template("operador-email.html")

@app.route("/painel-logs")
def painel_logs():
    return render_template("logs.html")

# =========================
# API FILA
# =========================
@app.route("/api/entrar_fila", methods=["POST"])
def entrar_fila():
    data = request.json
    cliente_id = str(uuid.uuid4())[:8]

    cliente = {
        "id": cliente_id,
        "nome": data.get("nome", f"Cliente_{len(fila_espera)+1}"),
        "timestamp": agora().strftime("%H:%M:%S"),
        "status": "espera",
    }

    fila_espera.append(cliente)

    return jsonify({
        "success": True,
        "cliente_id": cliente_id,
        "posicao": len(fila_espera)
    })

@app.route("/api/verificar_sala/<cliente_id>", methods=["GET"])
def verificar_sala(cliente_id):
    for sala_id, sala in salas_ativas.items():
        if sala["cliente_id"] == cliente_id:
            return jsonify({"sala_id": sala_id})
    return jsonify({"sala_id": None})

@app.route("/api/fila", methods=["GET"])
def get_fila():
    return jsonify({"clientes": fila_espera, "total": len(fila_espera)})

@app.route("/api/atender", methods=["POST"])
def atender():
    data = request.json
    cliente_id = data.get("cliente_id")
    operador = data.get("operador", "Operador")

    cliente = next((c for c in fila_espera if c["id"] == cliente_id), None)

    if cliente:
        fila_espera.remove(cliente)

        sala_id = f"sala_{cliente_id}_{int(agora().timestamp())}"
        salas_ativas[sala_id] = {
            "cliente_id": cliente_id,
            "operador": operador,
            "inicio": agora().strftime("%H:%M:%S"),
        }

        mensagens[sala_id] = []

        return jsonify({"success": True, "sala_id": sala_id, "cliente": cliente})

    return jsonify({"success": False}), 404

@app.route("/api/enviar_mensagem", methods=["POST"])
def enviar_mensagem():
    data = request.json
    sala_id = data.get("sala_id")
    de = data.get("de")
    texto = data.get("texto")

    if sala_id in mensagens:
        msg = {
            "de": de,
            "texto": texto,
            "timestamp": agora().strftime("%H:%M:%S"),
        }
        mensagens[sala_id].append(msg)
        return jsonify({"success": True, "mensagem": msg})

    return jsonify({"success": False}), 404

@app.route("/api/mensagens/<sala_id>", methods=["GET"])
def get_mensagens(sala_id):
    ultimo_index = int(request.args.get("ultimo", -1))

    if sala_id in mensagens:
        novas = mensagens[sala_id][ultimo_index + 1:]
        return jsonify({
            "mensagens": novas,
            "total": len(mensagens[sala_id])
        })

    return jsonify({"mensagens": []})

@app.route("/api/fechar", methods=["POST"])
def fechar():
    data = request.json
    sala_id = data.get("sala_id")

    if sala_id in salas_ativas:
        del salas_ativas[sala_id]
        if sala_id in mensagens:
            del mensagens[sala_id]
        return jsonify({"success": True})

    return jsonify({"success": False})

# =========================
# LOGS
# =========================
@app.route("/logs")
def get_logs():
    return jsonify(logs[::-1])

# =========================
# START
# =========================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
