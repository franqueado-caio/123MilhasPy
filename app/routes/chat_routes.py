# app/routes/chat_routes.py
from flask import Blueprint, request, jsonify
import uuid
import time
from collections import deque
from threading import Lock

chat_bp = Blueprint("chat", __name__)

# Estruturas em memória para o chat
fila_espera = []  # Lista de clientes aguardando
salas_ativas = {}  # Dict: cliente_id -> {sala_id, cliente_nome, operador, inicio}
mensagens_por_sala = {}  # Dict: sala_id -> lista de mensagens
_lock = Lock()


@chat_bp.route("/entrar_fila", methods=["POST"])
def entrar_fila():
    """Cliente entra na fila de espera"""
    try:
        data = request.json
        nome = data.get("nome", f"Cliente_{len(fila_espera) + 1}")
        cliente_id = str(uuid.uuid4())[:8]

        with _lock:
            # Verificar se já está na fila
            for cliente in fila_espera:
                if cliente["nome"] == nome:
                    return jsonify(
                        {
                            "success": True,
                            "cliente_id": cliente["id"],
                            "posicao": cliente.get("posicao", 1),
                            "status": "em_fila",
                            "message": f"Você já está na fila. Posição: {cliente.get('posicao', 1)}",
                        }
                    )

            cliente = {
                "id": cliente_id,
                "nome": nome,
                "entrada_timestamp": time.time(),
                "posicao": len(fila_espera) + 1,
            }
            fila_espera.append(cliente)

        return jsonify(
            {
                "success": True,
                "cliente_id": cliente_id,
                "posicao": len(fila_espera),
                "status": "em_fila",
                "message": f"Você entrou na fila. Posição: {len(fila_espera)}",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/verificar_sala/<cliente_id>", methods=["GET"])
def verificar_sala(cliente_id):
    """Verifica se o cliente já foi atendido"""
    try:
        with _lock:
            # Verificar se está em uma sala ativa
            if cliente_id in salas_ativas:
                sala = salas_ativas[cliente_id]
                return jsonify(
                    {
                        "status": "em_atendimento",
                        "sala_id": sala["sala_id"],
                        "operador": sala["operador"],
                    }
                )

            # Verificar posição na fila
            for idx, cliente in enumerate(fila_espera):
                if cliente["id"] == cliente_id:
                    return jsonify(
                        {
                            "status": "aguardando",
                            "posicao": idx + 1,
                            "total_fila": len(fila_espera),
                        }
                    )

            return jsonify({"status": "nao_encontrado"}), 404
    except Exception as e:
        return jsonify({"status": "erro", "error": str(e)}), 500


@chat_bp.route("/enviar_mensagem", methods=["POST"])
def enviar_mensagem():
    """Envia mensagem no chat"""
    try:
        data = request.json
        sala_id = data.get("sala_id")
        de = data.get("de")
        texto = data.get("texto")
        cliente_id = data.get("cliente_id")

        if not sala_id or not texto:
            return jsonify({"success": False, "message": "Dados incompletos"}), 400

        with _lock:
            if sala_id not in mensagens_por_sala:
                mensagens_por_sala[sala_id] = []

            msg = {
                "de": de,
                "texto": texto,
                "time": time.time(),
                "timestamp": time.strftime("%H:%M:%S"),
            }
            mensagens_por_sala[sala_id].append(msg)

        return jsonify(
            {
                "success": True,
                "mensagem": msg,
                "message": "Mensagem enviada com sucesso",
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/fila_espera", methods=["GET"])
def get_fila_espera():
    """Retorna a fila de espera para o dashboard do operador"""
    try:
        with _lock:
            clientes_formatados = []
            for idx, cliente in enumerate(fila_espera):
                clientes_formatados.append(
                    {
                        "id": cliente["id"],
                        "nome": cliente["nome"],
                        "posicao": idx + 1,
                        "tempo_espera": int(time.time() - cliente["entrada_timestamp"]),
                    }
                )

            # Calcular tempo médio de espera
            tempo_medio = 0
            if clientes_formatados:
                total_tempo = sum(c["tempo_espera"] for c in clientes_formatados)
                tempo_medio = total_tempo // len(clientes_formatados)

            return jsonify(
                {
                    "clientes": clientes_formatados,
                    "total": len(clientes_formatados),
                    "tempo_medio_espera": tempo_medio,
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/estatisticas", methods=["GET"])
def get_estatisticas():
    """Retorna estatísticas do chat para o dashboard"""
    try:
        with _lock:
            return jsonify(
                {
                    "total_em_fila": len(fila_espera),
                    "total_em_atendimento": len(salas_ativas),
                    "total_salas": len(salas_ativas),
                    "salas_ativas": list(salas_ativas.keys()),
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/atender_cliente", methods=["POST"])
def atender_cliente():
    """Atende um cliente da fila (operador puxa cliente)"""
    try:
        data = request.json
        cliente_id = data.get("cliente_id")
        operador = data.get("operador", "Operador")

        if not cliente_id:
            return (
                jsonify({"success": False, "message": "cliente_id é obrigatório"}),
                400,
            )

        with _lock:
            # Buscar cliente na fila
            cliente_encontrado = None
            for cliente in fila_espera:
                if cliente["id"] == cliente_id:
                    cliente_encontrado = cliente
                    fila_espera.remove(cliente)
                    break

            if not cliente_encontrado:
                return (
                    jsonify(
                        {"success": False, "message": "Cliente não encontrado na fila"}
                    ),
                    404,
                )

            # Criar sala
            sala_id = f"sala_{cliente_id}_{int(time.time())}"
            salas_ativas[cliente_id] = {
                "sala_id": sala_id,
                "cliente_id": cliente_id,
                "cliente_nome": cliente_encontrado["nome"],
                "operador": operador,
                "inicio_timestamp": time.time(),
                "inicio": time.strftime("%H:%M:%S"),
            }

            # Inicializar mensagens da sala
            mensagens_por_sala[sala_id] = [
                {
                    "de": "sistema",
                    "texto": f"🔔 {operador} entrou no chat",
                    "time": time.time(),
                    "timestamp": time.strftime("%H:%M:%S"),
                }
            ]

            return jsonify(
                {
                    "success": True,
                    "sala_id": sala_id,
                    "cliente": {"id": cliente_id, "nome": cliente_encontrado["nome"]},
                }
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/mensagens/<sala_id>", methods=["GET"])
def get_mensagens(sala_id):
    """Retorna mensagens de uma sala (para polling do operador)"""
    try:
        ultimo_timestamp = float(request.args.get("ultimo_timestamp", 0))

        with _lock:
            if sala_id not in mensagens_por_sala:
                return jsonify(
                    {
                        "mensagens": [],
                        "total_novas": 0,
                        "ultimo_timestamp": ultimo_timestamp,
                    }
                )

            mensagens = mensagens_por_sala[sala_id]
            novas = [m for m in mensagens if m.get("time", 0) > ultimo_timestamp]
            novo_timestamp = max(
                [m.get("time", 0) for m in mensagens], default=ultimo_timestamp
            )

            return jsonify(
                {
                    "mensagens": novas,
                    "total_novas": len(novas),
                    "ultimo_timestamp": novo_timestamp,
                }
            )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/fechar_sala", methods=["POST"])
def fechar_sala():
    """Fecha uma sala de chat"""
    try:
        data = request.json
        sala_id = data.get("sala_id")

        if not sala_id:
            return jsonify({"success": False, "message": "sala_id é obrigatório"}), 400

        with _lock:
            # Encontrar e remover a sala
            cliente_remover = None
            for cliente_id, sala in salas_ativas.items():
                if sala["sala_id"] == sala_id:
                    cliente_remover = cliente_id
                    break

            if cliente_remover:
                del salas_ativas[cliente_remover]

            # Limpar mensagens da sala
            if sala_id in mensagens_por_sala:
                del mensagens_por_sala[sala_id]

            return jsonify({"success": True, "message": "Sala fechada com sucesso"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/salas_ativas", methods=["GET"])
def get_salas_ativas():
    """Retorna lista de todas as salas ativas"""
    try:
        with _lock:
            salas = []
            for cliente_id, sala in salas_ativas.items():
                # Calcular tempo de atendimento
                tempo_atendimento = int(
                    time.time() - sala.get("inicio_timestamp", time.time())
                )

                salas.append(
                    {
                        "sala_id": sala["sala_id"],
                        "cliente_id": cliente_id,
                        "cliente_nome": sala["cliente_nome"],
                        "operador": sala["operador"],
                        "inicio": sala.get("inicio", time.strftime("%H:%M:%S")),
                        "tempo_atendimento": tempo_atendimento,
                        "status": "ativo",
                    }
                )

            return jsonify({"salas": salas, "total": len(salas)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/status_cliente/<cliente_id>", methods=["GET"])
def status_cliente(cliente_id):
    """Verifica status de um cliente específico"""
    return verificar_sala(cliente_id)
