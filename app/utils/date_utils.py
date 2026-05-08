from datetime import datetime
import pytz


def get_brasilia_time():
    """Retorna datetime atual no horário de Brasília"""
    return datetime.now(pytz.timezone("America/Sao_Paulo"))


def format_brasilia_time(dt=None):
    """Formata data/hora no padrão brasileiro"""
    if dt is None:
        dt = get_brasilia_time()
    return dt.strftime("%d/%m/%Y %H:%M:%S")


def iso_to_brasilia(iso_string):
    """Converte ISO string para horário Brasília"""
    dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
    return dt.astimezone(pytz.timezone("America/Sao_Paulo"))
