import uuid
import hashlib
import secrets
from datetime import datetime, timedelta


def generate_tracking_token():
    """Gera token único para tracking"""
    return secrets.token_urlsafe(32)


def generate_session_id():
    """Gera ID de sessão único"""
    return str(uuid.uuid4())


def generate_tracking_cookie():
    """Gera cookie de tracking"""
    token = generate_tracking_token()
    session_id = generate_session_id()
    return {
        "token": token,
        "session_id": session_id,
        "created_at": datetime.utcnow().isoformat(),
    }


def hash_cpf(cpf):
    """Cria hash do CPF para consultas sem expor dados sensíveis"""
    return hashlib.sha256(cpf.encode()).hexdigest()[:16]
