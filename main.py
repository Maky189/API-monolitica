from gateway import Gateway
from monolith import Monolith
from payment_service import PaymentService
from logger_config import setup_logging

setup_logging()

payment_service = PaymentService()
monolith = Monolith(payment_service)
gateway = Gateway(monolith)

response = gateway.handle_request(
    "/api/orders",
    {"item": "Mouse", "price": 50}
)

print("\nResposta final:", response)