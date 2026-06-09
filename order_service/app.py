import itertools
import logging
import os
import sys
import threading

sys.path.insert(0, "/app")
from logger_config import setup_logging
setup_logging()

import requests
from functools import wraps
from flask import Flask, request, jsonify
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from repository import Repository, init_db

logger = logging.getLogger("OrderService")

app = Flask(__name__)

INTERNAL_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "internal-secret-change-me")

PAYMENT_SERVICE_URLS = [
    u.strip()
    for u in os.environ.get(
        "PAYMENT_SERVICE_URLS", "http://payment1:5003/payment"
    ).split(",")
    if u.strip()
]
PAYMENT_TIMEOUT = float(os.environ.get("PAYMENT_TIMEOUT_SECONDS", "3"))

_rr_lock = threading.Lock()
_rr_cycle = itertools.cycle(PAYMENT_SERVICE_URLS)

init_db()
repository = Repository()


def require_internal_token(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("X-Internal-Token", "")
        if token != INTERNAL_TOKEN:
            logger.warning("Tentativa de acesso com token interno inválido")
            return jsonify({"error": "Acesso não autorizado"}), 403
        return f(*args, **kwargs)
    return decorated


def _next_payment_url():
    with _rr_lock:
        return next(_rr_cycle)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, max=2),
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    reraise=True,
)
def _call_payment(order):
    url = _next_payment_url()
    logger.info(f"load balancer -> {url}")
    response = requests.post(
        url,
        json=order,
        headers={"X-Internal-Token": INTERNAL_TOKEN},
        timeout=PAYMENT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


@app.route("/orders", methods=["POST"])
@require_internal_token
def create_order():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Body inválido"}), 400

    idempotency_key = request.headers.get("Idempotency-Key")
    if idempotency_key:
        cached = repository.get_idempotent_response(idempotency_key)
        if cached is not None:
            logger.info(f"Retornando resposta idempotente para chave {idempotency_key}")
            return jsonify(cached), 200

    order = {"item": data["item"], "price": data["price"]}
    order["id"] = repository.save_order(order)
    logger.info(f"Pedido criado: id={order['id']}")

    payment_instance = None
    try:
        payment_response = _call_payment(order)
        payment_status = payment_response["status"]
        payment_instance = payment_response.get("instance")
    except requests.RequestException as exc:
        logger.error(f"Falha ao chamar payment-service: {exc}")
        payment_status = "UNKNOWN"

    logger.info(f"Pagamento {payment_status} (instância: {payment_instance})")

    result = {
        "order": order,
        "payment_status": payment_status,
        "payment_instance": payment_instance,
    }

    if idempotency_key:
        repository.save_idempotent_response(idempotency_key, result)

    return jsonify(result), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
