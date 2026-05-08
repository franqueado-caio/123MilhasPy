from app import db
from datetime import datetime
import pytz
import uuid


def get_brasilia_time():
    return datetime.now(pytz.timezone("America/Sao_Paulo"))


class TrackingVisit(db.Model):
    __tablename__ = "tracking_visits"

    id = db.Column(db.Integer, primary_key=True)
    tracking_id = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    token = db.Column(db.String(64), unique=True, index=True)

    # Dados do usuário
    nome = db.Column(db.String(200))
    cpf = db.Column(db.String(14), index=True)
    email = db.Column(db.String(200), index=True)

    # Dados da transferência
    banco_codigo = db.Column(db.String(10))
    banco_nome = db.Column(db.String(100))
    agencia = db.Column(db.String(20))
    conta = db.Column(db.String(30))
    valor_transferencia = db.Column(db.Float)
    status_transferencia = db.Column(db.String(20), default="pendente")

    # Dados do dispositivo
    dispositivo_tipo = db.Column(db.String(20))  # mobile, tablet, desktop
    dispositivo_os = db.Column(db.String(50))  # Windows, MacOS, Linux, Android, iOS
    dispositivo_browser = db.Column(db.String(50))
    dispositivo_resolucao = db.Column(db.String(20))
    user_agent = db.Column(db.Text)

    # Dados de rede
    ip_address = db.Column(db.String(45))
    ip_forwarded = db.Column(db.String(45))

    # Dados de navegação
    pagina_entrada = db.Column(db.String(500))
    pagina_atual = db.Column(db.String(500))
    pagina_saida = db.Column(db.String(500))
    url_referrer = db.Column(db.String(500))

    # Controle de fluxo
    campanha_id = db.Column(db.String(100), index=True)
    session_id = db.Column(db.String(64), index=True)
    flow_completed = db.Column(db.Boolean, default=False)
    current_step = db.Column(db.Integer, default=1)

    # Timestamps (horário Brasil)
    created_at = db.Column(db.DateTime, default=get_brasilia_time)
    updated_at = db.Column(
        db.DateTime, default=get_brasilia_time, onupdate=get_brasilia_time
    )
    last_activity = db.Column(
        db.DateTime, default=get_brasilia_time, onupdate=get_brasilia_time
    )

    # Metadados
    metadata_json = db.Column(db.JSON, default={})

    # Relacionamentos
    events = db.relationship("TrackingEvent", backref="visit", lazy="dynamic")
    transferencias = db.relationship(
        "TransferenciaRegistro", backref="visit", lazy="dynamic"
    )

    def to_dict(self):
        return {
            "id": self.tracking_id,
            "nome": self.nome,
            "cpf": self.cpf,
            "email": self.email,
            "dispositivo": {
                "tipo": self.dispositivo_tipo,
                "os": self.dispositivo_os,
                "browser": self.dispositivo_browser,
                "resolucao": self.dispositivo_resolucao,
            },
            "status_transferencia": self.status_transferencia,
            "flow_completed": self.flow_completed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_activity": (
                self.last_activity.isoformat() if self.last_activity else None
            ),
        }


class TrackingEvent(db.Model):
    __tablename__ = "tracking_events"

    id = db.Column(db.Integer, primary_key=True)
    tracking_id = db.Column(db.Integer, db.ForeignKey("tracking_visits.id"), index=True)

    event_type = db.Column(
        db.String(50), index=True
    )  # page_view, click, form_submit, transfer_attempt
    event_name = db.Column(db.String(100))
    page_url = db.Column(db.String(500))
    page_title = db.Column(db.String(200))
    element_id = db.Column(db.String(100))
    element_class = db.Column(db.String(200))

    # Dados adicionais
    event_data = db.Column(db.JSON, default={})

    timestamp = db.Column(db.DateTime, default=get_brasilia_time, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.event_type,
            "name": self.event_name,
            "page": self.page_url,
            "data": self.event_data,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
