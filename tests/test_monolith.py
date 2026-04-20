import unittest
from monolith import Monolith

class FakePaymentService:
    def process_payment(self, order):
        return "APROVED"
    
class TestMonolith(unittest.TestCase):
    def test_create_order_sucess(self):
        service = FakePaymentService()
        monolith = Monolith(service)
        
        data = {"item": "mouse", "price": 250}
        result = monolith.create_order(data)
        
        self.assertEqual(result["payment_status"], "APROVED")
        self.assertEqual(result["order"]["item"], "mouse")
        
if __name__ == "__main__":
    unittest.main()