import logging
import requests

logger = logging.getLogger("Monolith")

PAYMENT_SERVICE_URL = "http://localhost:5001/payment"

class Monolith:
    def create_order(self, data):
        logger.info("criando pedido")
        
        order = {
            "id": 1,
            "item": data.get("item"),
            "price": data.get("price")
        }
        
        logger.info(f"pedido criado: {order}")
        
        logger.info("chamando microserviço de pagamento")
        response = requests.post(PAYMENT_SERVICE_URL, json = order)
        payment_status = response.json()["status"]
        
        logger.info(f"status do pagamento: {payment_status}")
        
        return {
            "order": order,
            "payment_status": payment_status
        }