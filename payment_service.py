import logging

logger = logging.getLogger("PaymentService")

class PaymentService:
    def process_payment(self, order):
        logger.info(f"processando pagamento")
        
        if order["price"] > 0:
            logger.info("pagamento aprovado")
            return "APROVED"
        else:
            logger.warning("pagamento recusado")
            return "REJECTED"