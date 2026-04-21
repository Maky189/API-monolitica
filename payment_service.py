import logging
from flask import Flask, request, jsonify

logger = logging.getLogger("PaymentService")

app = Flask(__name__)

@app.route("/payment", methods = ["POST"])
def payment():
    order = request.get_json()
    logger.info(f"processando pagamento")
    
    if order["price"] > 0:
        logger.info("pagamento aprovado")
        return jsonify({"status": "APPROVED"})
    else:
        logger.warning("pagamento recusado")
        return jsonify({"status": "REJECTED"})
    
if __name__ == "__main__":
    app.run(port = 5001)