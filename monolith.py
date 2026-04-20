import logging

logger = logging.getLogger("Monolith")

class Monolith:
    def __init__(self, payment_service):
        self.payment_service = payment_service
        
    def create_order(self, data):
        logger.info("criando pedido")
        
        order = {
            "id": 1,
            "item": data.get("item"),
            "price": data.get("price")
        }
        
        logger.info(f"pedido criado: {order}")
        
        logger.info("chamando microserviço de pagamento")
        payment_status = self.payment_service.process_payment(order)
        
        logger.info(f"status do pagamento: {payment_status}")
        
        return {
            "order": order,
            "payment_status": payment_status
        }