# app/routes/short_routes.py
from flask import Blueprint, request, redirect
import sqlite3
from user_agents import parse

short_bp = Blueprint("short", __name__)

@short_bp.route("/s/<short_code>", methods=["GET"])
def redirect_short(short_code):
    """Redireciona links curtos e registra o clique"""
    try:
        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        # Garantir que a tabela short_links existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS short_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE,
                original_url TEXT,
                created_at TEXT
            )
        """)

        # Garantir que a tabela link_clicks existe (SOMENTE com colunas corretas)
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
        cursor.execute("SELECT original_url FROM short_links WHERE short_code = ?", (short_code,))
        row = cursor.fetchone()

        if not row or not row[0]:
            conn.close()
            return "Link não encontrado", 404

        original_url = row[0]

        # Detectar dispositivo
        user_agent_string = request.headers.get('User-Agent', '')
        ua = parse(user_agent_string)

        device_type = "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop"

        # Registrar o clique (APENAS colunas que existem na tabela)
        cursor.execute("""
            INSERT INTO link_clicks (short_code, original_url, clicked_at, ip_address, user_agent, device_type)
            VALUES (?, ?, datetime('now', 'localtime'), ?, ?, ?)
        """, (short_code, original_url, request.remote_addr, user_agent_string[:500], device_type))

        conn.commit()
        conn.close()

        print(f"🔗 Link {short_code} clicado! Device: {device_type}, IP: {request.remote_addr}")
        return redirect(original_url)

    except Exception as e:
        print(f"❌ Erro ao redirecionar: {e}")
        return "Erro ao redirecionar", 500
