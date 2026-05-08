# db.py - Utilitário para operações com banco
import sqlite3
import json
import uuid
from datetime import datetime
import pytz

DB_PATH = "123milhas.db"


def get_connection():
    """Retorna conexão com o banco"""
    return sqlite3.connect(DB_PATH)


def get_brasilia_time():
    return datetime.now(pytz.timezone("America/Sao_Paulo"))


# Funções para Tracking
def create_tracking_visit(data):
    conn = get_connection()
    cursor = conn.cursor()

    tracking_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO tracking_visits (
            tracking_id, token, nome, cpf, email, dispositivo_tipo,
            dispositivo_os, dispositivo_browser, user_agent, ip_address,
            pagina_entrada, campanha_id, session_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            tracking_id,
            data.get("token"),
            data.get("nome"),
            data.get("cpf"),
            data.get("email"),
            data.get("dispositivo_tipo"),
            data.get("dispositivo_os"),
            data.get("dispositivo_browser"),
            data.get("user_agent"),
            data.get("ip_address"),
            data.get("pagina_entrada"),
            data.get("campanha_id"),
            data.get("session_id"),
        ),
    )

    conn.commit()
    conn.close()
    return tracking_id


def update_tracking_user(tracking_id, nome, cpf, email):
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


# Funções para Transferências
def register_transfer_attempt(data):
    conn = get_connection()
    cursor = conn.cursor()

    transferencia_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO transferencias_registro (
            transferencia_id, tracking_id, banco_codigo, banco_nome,
            agencia, conta, valor, status, tentativas
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            transferencia_id,
            data.get("tracking_id"),
            data.get("banco_codigo"),
            data.get("banco_nome"),
            data.get("agencia"),
            data.get("conta"),
            data.get("valor"),
            "pendente",
            1,
        ),
    )

    conn.commit()
    conn.close()
    return transferencia_id


# Funções para Chat
def create_chat_sala(cliente_id, cliente_nome):
    conn = get_connection()
    cursor = conn.cursor()

    sala_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO chat_salas (sala_id, cliente_id, cliente_nome, status)
        VALUES (?, ?, ?, 'aguardando')
    """,
        (sala_id, cliente_id, cliente_nome),
    )

    conn.commit()
    conn.close()
    return sala_id


def add_chat_message(sala_id, de, texto):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO chat_mensagens (sala_id, de, texto)
        VALUES (?, ?, ?)
    """,
        (sala_id, de, texto),
    )
    conn.commit()
    conn.close()


def get_chat_messages(sala_id, limit=50):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT de, texto, timestamp FROM chat_mensagens
        WHERE sala_id = ? ORDER BY timestamp ASC LIMIT ?
    """,
        (sala_id, limit),
    )
    messages = cursor.fetchall()
    conn.close()
    return [{"de": m[0], "texto": m[1], "timestamp": m[2]} for m in messages]
