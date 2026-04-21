import logging
from flask import Flask, request, jsonify
from monolith import Monolith

logger = logging.getLogger("Gateway")

app = Flask(__name__)
monolith = Monolith()

@app.route("/api/orders", methods = ["POST"])

def handle_orders():
    logger.info("Recebendo requisiçao: /api/orders")
    logger.info("Encaminhando para o monolito")
    data = request.get_json()
    result = monolith.create_order(data)
    return jsonify(result)

@app.errorhandler(404)
def not_found(e):
    logger.error("Rota nao encontrada")
    return jsonify({"error": "Not found"}), 404

if __name__ == "__main__":
    app.run(port = 5000)