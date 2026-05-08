# db_utils.py
import sqlite3
import uuid
from datetime import datetime
import pytz

DB_PATH = "123milhas.db"


def get_brasilia_time():
    return datetime.now(pytz.timezone("America/Sao_Paulo"))


def get_connection():
    return sqlite3.connect(DB_PATH)


def registrar_tentativa_transferencia(dados):
    """Registra uma tentativa de transferência no banco"""
    conn = get_connection()
    cursor = conn.cursor()

    transferencia_id = str(uuid.uuid4())

    cursor.execute(
        """
        INSERT INTO transferencias_registro (
            transferencia_id, tracking_id, banco_codigo, banco_nome,
            agencia, conta, valor, valor_original_total, numero_cota,
            status, mensagem_retorno, tentativas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            transferencia_id,
            dados.get("tracking_id"),
            dados.get("banco_codigo"),
            dados.get("banco_nome"),
            dados.get("agencia"),
            dados.get("conta"),
            dados.get("valor"),
            dados.get("valor_original_total"),
            dados.get("numero_cota"),
            "pendente_verificacao",
            "Aguardando contato com atendente",
            1,
        ),
    )

    conn.commit()
    conn.close()
    print(f"✅ Transferência registrada: {transferencia_id}")
    return transferencia_id


def registrar_visita(dados):
    """Registra uma nova visita no tracking"""
    conn = get_connection()
    cursor = conn.cursor()

    tracking_id = str(uuid.uuid4())

    cursor.execute(
        """
        INSERT INTO tracking_visits (
            tracking_id, session_id, campanha_id, pagina_entrada,
            dispositivo_tipo, dispositivo_os, dispositivo_browser,
            user_agent, ip_address
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            tracking_id,
            dados.get("session_id"),
            dados.get("campanha_id"),
            dados.get("pagina_entrada"),
            dados.get("dispositivo_tipo"),
            dados.get("dispositivo_os"),
            dados.get("dispositivo_browser"),
            dados.get("user_agent"),
            dados.get("ip_address"),
        ),
    )

    conn.commit()
    conn.close()
    print(f"✅ Visita registrada: {tracking_id}")
    return tracking_id


def atualizar_dados_usuario(tracking_id, nome, cpf, email):
    """Atualiza os dados do usuário no tracking"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE tracking_visits 
        SET nome = ?, cpf = ?, email = ?, updated_at = CURRENT_TIMESTAMP
        WHERE tracking_id = ?
    """,
        (nome, cpf, email, tracking_id),
    )
    conn.commit()
    conn.close()
    print(f"✅ Dados do usuário atualizados para: {nome}")


def buscar_transferencias_por_cpf(cpf):
    """Busca transferências de um usuário pelo CPF"""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT t.* FROM transferencias_registro t
        JOIN tracking_visits v ON t.tracking_id = v.tracking_id
        WHERE v.cpf = ?
        ORDER BY t.created_at DESC
    """,
        (cpf,),
    )

    results = cursor.fetchall()
    conn.close()
    return results
