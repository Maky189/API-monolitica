import logging

logger = logging.getLogger("Gateway")

class Gateway:
    def __init__(self, monolith):
        self.monolith = monolith

    def handle_request(self, path, data):
        logger.info(f"Recebendo requisição: {path}")

        if path == "/api/orders":
            logger.info("Encaminhando para o Monólito")
            return self.monolith.create_order(data)
        else:
            logger.error("Rota não encontrada")
            return {"error": "Not found"}