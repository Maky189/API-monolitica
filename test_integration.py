import unittest
from gateway import Gateway
from monolith import Monolith
from payment_service import PaymentService

class TestIntegration(unittest.TestCase):

    def test_full_flow(self):
        payment_service = PaymentService()
        monolith = Monolith(payment_service)
        gateway = Gateway(monolith)

        response = gateway.handle_request(
            "/api/orders",
            {"item": "Headset", "price": 200}
        )

        self.assertEqual(response["payment_status"], "APPROVED")

    def test_payment_rejected(self):
        payment_service = PaymentService()
        monolith = Monolith(payment_service)
        gateway = Gateway(monolith)

        response = gateway.handle_request(
            "/api/orders",
            {"item": "Headset", "price": 0}
        )

        self.assertEqual(response["payment_status"], "REJECTED")

if __name__ == "__main__":
    unittest.main()