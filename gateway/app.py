import logging
import os
import sys

sys.path.insert(0, "/app")
from logger_config import setup_logging
setup_logging()

import jwt
import requests
from functools import wraps
from flask import Flask, request, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

logger = logging.getLogger("Gateway")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024  # 1 MB

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
ORDER_SERVICE_URL = os.environ.get("ORDER_SERVICE_URL", "http://order-service:5001")
INTERNAL_TOKEN = os.environ.get("INTERNAL_SERVICE_TOKEN", "internal-secret-change-me")
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "*")

CORS(app, resources={r"/api/*": {"origins": ALLOWED_ORIGINS}})

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["500 per day", "100 per hour"],
    storage_uri="memory://",
)


@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Powered-By"] = ""
    response.headers.pop("Server", None)
    return response


def require_jwt(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Token de autenticação ausente"}), 401
        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            g.current_user = payload["sub"]
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expirado"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Token inválido"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/api/orders", methods=["POST"])
@limiter.limit("20 per minute")
@require_jwt
def handle_orders():
    logger.info(f"[{g.current_user}] POST /api/orders")

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Body JSON inválido ou ausente"}), 400

    if "item" not in data or "price" not in data:
        return jsonify({"error": "Campos 'item' e 'price' são obrigatórios"}), 400

    item = str(data["item"]).strip()[:255]
    if not item:
        return jsonify({"error": "'item' não pode ser vazio"}), 400
    try:
        price = float(data["price"])
    except (ValueError, TypeError):
        return jsonify({"error": "'price' deve ser um número"}), 400

    idempotency_key = request.headers.get("Idempotency-Key")
    headers = {
        "X-Internal-Token": INTERNAL_TOKEN,
        "X-User": g.current_user,
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    try:
        resp = requests.post(
            f"{ORDER_SERVICE_URL}/orders",
            json={"item": item, "price": price},
            headers=headers,
            timeout=10,
        )
        return jsonify(resp.json()), resp.status_code
    except requests.RequestException as exc:
        logger.error(f"Erro ao chamar order-service: {exc}")
        return jsonify({"error": "Serviço indisponível"}), 503


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Rota não encontrada"}), 404


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Método HTTP não permitido"}), 405


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return jsonify({"error": "Muitas requisições. Tente novamente mais tarde."}), 429


@app.errorhandler(413)
def request_too_large(e):
    return jsonify({"error": "Requisição muito grande (máximo 1MB)"}), 413


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
