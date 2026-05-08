#!/usr/bin/env python
"""Ponto de entrada da aplicação 123Milhas"""

from app import create_app, db
from flask_migrate import Migrate
import os

# Criar aplicação
app = create_app(os.environ.get("FLASK_CONFIG", "default"))
migrate = Migrate(app, db)


@app.shell_context_processor
def make_shell_context():
    """Contexto para o shell do Flask"""
    return {
        "app": app,
        "db": db,
        # Models
        "TrackingVisit": __import__(
            "app.models.tracking", fromlist=["TrackingVisit"]
        ).TrackingVisit,
        "TrackingEvent": __import__(
            "app.models.tracking", fromlist=["TrackingEvent"]
        ).TrackingEvent,
        "TransferenciaRegistro": __import__(
            "app.models.transferencia", fromlist=["TransferenciaRegistro"]
        ).TransferenciaRegistro,
    }


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
