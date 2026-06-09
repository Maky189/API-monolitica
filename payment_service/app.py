import logging
import os
import socket
import sys

sys.path.insert(0, "/app")
from logger_config import setup_logging
setup_logging()

from functools import wraps
from flask import Flask, request, jsonify

logger = logging.getLogger("PaymentService")

app = Flask(__name__)

INSTANCE_ID = os.environ.get("INSTANCE_ID", socket.gethostname())
INTERNAL_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "internal-secret-change-me")


def require_internal_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Internal-Token", "")
        if token != INTERNAL_TOKEN:
            logger.warning(f"[{INSTANCE_ID}] Acesso não autorizado")
            return jsonify({"error": "Acesso não autorizado"}), 403
        return f(*args, **kwargs)
    return decorated


@app.route("/payment", methods=["POST"])
@require_internal_token
def payment():
    order = request.get_json(silent=True)
    if not order:
        return jsonify({"error": "Body inválido"}), 400

    order_id = order.get("id")
    price = order.get("price", 0)

    logger.info(f"[{INSTANCE_ID}] processando pagamento order_id={order_id}")

    status = "APPROVED" if price > 0 else "REJECTED"
    logger.info(f"[{INSTANCE_ID}] pagamento {status}")

    return jsonify({"status": status, "instance": INSTANCE_ID})


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "instance": INSTANCE_ID}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
