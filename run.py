#!/usr/bin/env python
"""Ponto de entrada da aplicação 123Milhas"""

from app import create_app, db
from flask_migrate import Migrate
from flask import request  # ← IMPORTANTE!
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


@app.after_request
def add_header(response):
    """Adiciona headers para cache de CSS/JS"""
    if request.path.startswith("/static/"):
        # CSS e JS ficam em cache por 30 dias
        response.cache_control.max_age = 2592000
        response.cache_control.public = True
    else:
        # HTML não fica em cache
        response.cache_control.no_cache = True
        response.cache_control.no_store = True
        response.cache_control.must_revalidate = True
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
