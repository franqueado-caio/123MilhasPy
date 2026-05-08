from app import db
from app.models.tracking import get_brasilia_time
import uuid


class TransferenciaRegistro(db.Model):
    __tablename__ = "transferencias_registro"

    id = db.Column(db.Integer, primary_key=True)
    transferencia_id = db.Column(
        db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4())
    )
    tracking_id = db.Column(db.Integer, db.ForeignKey("tracking_visits.id"), index=True)

    # Dados bancários
    banco_codigo = db.Column(db.String(10), nullable=False)
    banco_nome = db.Column(db.String(100), nullable=False)
    agencia = db.Column(db.String(20), nullable=False)
    conta = db.Column(db.String(30), nullable=False)

    # Dados da transferência
    valor = db.Column(db.Float, nullable=False)
    valor_original_total = db.Column(db.Float)
    numero_cota = db.Column(db.Integer)

    # Status
    status = db.Column(
        db.String(20), default="pendente"
    )  # pendente, processando, concluido, recusado, erro
    mensagem_retorno = db.Column(db.Text)

    # Tentativas
    tentativas = db.Column(db.Integer, default=1)

    # Timestamps
    created_at = db.Column(db.DateTime, default=get_brasilia_time)
    updated_at = db.Column(
        db.DateTime, default=get_brasilia_time, onupdate=get_brasilia_time
    )

    def to_dict(self):
        return {
            "id": self.transferencia_id,
            "banco": self.banco_nome,
            "agencia": self.agencia,
            "conta": self.conta,
            "valor": self.valor,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
