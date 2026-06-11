import datetime
import logging
import os
import sys

sys.path.insert(0, "/app")
from logger_config import setup_logging
setup_logging()

import jwt
from flask import Flask, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash

logger = logging.getLogger("AuthService")

app = Flask(__name__)

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))

# In production: replace with a real user database
_RAW_USERS = {
    "admin": os.environ.get("ADMIN_PASSWORD", "admin123"),
    "user": os.environ.get("USER_PASSWORD", "user123"),
}
USERS = {username: generate_password_hash(pw) for username, pw in _RAW_USERS.items()}


@app.route("/auth/token", methods=["POST"])
def get_token():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Body JSON inválido"}), 400

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username e password são obrigatórios"}), 400

    hashed = USERS.get(username)
    if not hashed or not check_password_hash(hashed, password):
        logger.warning(f"Tentativa de login inválida para '{username}'")
        return jsonify({"error": "Credenciais inválidas"}), 401

    now = datetime.datetime.utcnow()
    payload = {
        "sub": username,
        "iat": now,
        "exp": now + datetime.timedelta(hours=JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    logger.info(f"Token emitido para '{username}'")
    return jsonify({"token": token, "expires_in": JWT_EXPIRY_HOURS * 3600}), 200


@app.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"}), 200


@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Método HTTP não permitido"}), 405


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
