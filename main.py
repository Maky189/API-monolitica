import time
import threading
import requests
from logger_config import setup_logging

setup_logging()

# inicia o PaymentService em background
def start_payment_service():
    import payment_service
    payment_service.app.run(port = 5001, use_reloader = False)

# inicia o Gateway em background
def start_gateway():
    import gateway
    gateway.app.run(port = 5000, use_reloader = False)

threading.Thread(target = start_payment_service, daemon = True).start()
threading.Thread(target = start_gateway, daemon = True).start()

# Aguarda os servidores iniciarem
time.sleep(1)

# Faz a requisição HTTP real ao Gateway
response = requests.post(
    "http://localhost:5000/api/orders",
    json={"item": "Mouse", "price": 50}
)

print("\nResposta final:", response.json()) 