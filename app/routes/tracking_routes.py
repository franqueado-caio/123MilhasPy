# app/routes/tracking_routes.py
from flask import Blueprint, request, jsonify, make_response, redirect, abort
import sqlite3
import uuid
import json
from user_agents import parse
from datetime import datetime
import pytz

tracking_bp = Blueprint("tracking", __name__)

# ============================================
# FUNÇÕES AUXILIARES
# ============================================


def get_brasilia_time():
    return datetime.now(pytz.timezone("America/Sao_Paulo"))


# ============================================
# ROTAS DE TRACKING
# ============================================


@tracking_bp.route("/init", methods=["POST"])
def init_tracking():
    """Inicializa tracking do usuário"""
    try:
        data = request.json or {}

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        tracking_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        user_agent = request.headers.get("User-Agent", "")
        ip_address = request.remote_addr

        ua = parse(user_agent)
        dispositivo_tipo = (
            "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop"
        )
        dispositivo_os = ua.os.family if ua.os.family else "unknown"
        dispositivo_browser = ua.browser.family if ua.browser.family else "unknown"

        cursor.execute(
            """
            INSERT INTO tracking_visits (
                tracking_id, session_id, campanha_id, pagina_entrada,
                dispositivo_tipo, dispositivo_os, dispositivo_browser, user_agent, ip_address,
                created_at, last_activity
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
        """,
            (
                tracking_id,
                session_id,
                data.get("campanha_id"),
                data.get("pagina_entrada", "/"),
                dispositivo_tipo,
                dispositivo_os,
                dispositivo_browser,
                user_agent,
                ip_address,
            ),
        )

        conn.commit()
        conn.close()

        response = make_response(
            jsonify(
                {"success": True, "tracking_id": tracking_id, "session_id": session_id}
            )
        )
        response.set_cookie(
            "tracking_id", tracking_id, max_age=30 * 24 * 60 * 60, httponly=True
        )
        return response
    except Exception as e:
        print(f"❌ Erro init_tracking: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@tracking_bp.route("/update_user", methods=["POST"])
def update_user():
    """Atualiza dados do usuário"""
    try:
        data = request.json
        tracking_id = data.get("tracking_id") or request.cookies.get("tracking_id")

        if not tracking_id:
            return jsonify({"success": False, "error": "tracking_id required"}), 400

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        cpf = data.get("cpf", "")
        cpf_limpo = cpf.replace(".", "").replace("-", "") if cpf else None

        cursor.execute(
            """
            UPDATE tracking_visits 
            SET nome = ?, cpf = ?, email = ?, updated_at = datetime('now', 'localtime')
            WHERE tracking_id = ?
        """,
            (data.get("nome"), cpf_limpo, data.get("email"), tracking_id),
        )

        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@tracking_bp.route("/visit/<tracking_id>", methods=["GET"])
def get_visit(tracking_id):
    """Consulta informações da visita"""
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT tracking_id, nome, cpf, email, dispositivo_tipo, 
                   dispositivo_os, dispositivo_browser, user_agent, ip_address,
                   created_at, last_activity
            FROM tracking_visits 
            WHERE tracking_id = ?
        """,
            (tracking_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return jsonify(
                {
                    "success": True,
                    "visit": {
                        "tracking_id": row["tracking_id"],
                        "nome": row["nome"] or "N/A",
                        "cpf": row["cpf"] or "N/A",
                        "email": row["email"] or "N/A",
                        "dispositivo": f"{row['dispositivo_tipo']} - {row['dispositivo_os']}",
                        "navegador": row["dispositivo_browser"] or "N/A",
                        "ip": row["ip_address"] or "N/A",
                        "user_agent": row["user_agent"] or "N/A",
                        "data_criacao": row["created_at"],
                        "ultima_atividade": row["last_activity"],
                    },
                }
            )
        return jsonify({"success": False, "error": "Not found"}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTA DE REDIRECIONAMENTO DE LINK CURTO
# ============================================


@tracking_bp.route("/s/<short_code>", methods=["GET"])
def redirect_short(short_code):
    """Redireciona links curtos e registra o clique"""
    try:
        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        # Garantir que a tabela existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS short_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE,
                original_url TEXT,
                created_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS link_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT,
                original_url TEXT,
                clicked_at TEXT,
                ip_address TEXT,
                user_agent TEXT,
                device_type TEXT
            )
        """)
        conn.commit()

        # Buscar a URL original
        cursor.execute(
            "SELECT original_url FROM short_links WHERE short_code = ?", (short_code,)
        )
        row = cursor.fetchone()

        if not row or not row[0]:
            conn.close()
            return "Link não encontrado", 404

        original_url = row[0]

        # Detectar dispositivo
        user_agent_string = request.headers.get("User-Agent", "")
        ua = parse(user_agent_string)

        if ua.is_mobile:
            device_type = "mobile"
        elif ua.is_tablet:
            device_type = "tablet"
        else:
            device_type = "desktop"

        # Registrar o clique
        cursor.execute(
            """
            INSERT INTO link_clicks (short_code, original_url, clicked_at, ip_address, user_agent, device_type)
            VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?)
        """,
            (
                short_code,
                original_url,
                request.remote_addr,
                user_agent_string[:500],
                device_type,
            ),
        )

        conn.commit()
        conn.close()

        print(
            f"🔗 Link {short_code} clicado! Dispositivo: {device_type}, IP: {request.remote_addr}"
        )
        return redirect(original_url)

    except Exception as e:
        print(f"Erro ao redirecionar: {e}")
        return "Erro ao redirecionar", 500


# ============================================
# ROTAS DE CONSULTA DE CLICK (OPCIONAL)
# ============================================


@tracking_bp.route("/cliques", methods=["GET"])
def consultar_cliques():
    """Consulta todos os cliques em links curtos"""
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 
                short_code,
                original_url,
                clicked_at,
                ip_address,
                device_type
            FROM link_clicks
            ORDER BY clicked_at DESC
            LIMIT 100
        """)

        rows = cursor.fetchall()
        conn.close()

        cliques = [dict(row) for row in rows]

        return jsonify({"success": True, "total": len(cliques), "cliques": cliques})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
