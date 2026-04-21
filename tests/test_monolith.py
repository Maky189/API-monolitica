import unittest
from unittest.mock import patch, Mock
from monolith import Monolith

class TestMonolith(unittest.TestCase):

    @patch("monolith.requests.post")
    def test_create_order_success(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.json.return_value = {"status": "APPROVED"}

        monolith = Monolith()
        result = monolith.create_order({"item": "mouse", "price": 250})

        self.assertEqual(result["payment_status"], "APPROVED")
        self.assertEqual(result["order"]["item"], "mouse")

    @patch("monolith.requests.post")
    def test_create_order_rejected(self, mock_post):
        mock_post.return_value = Mock(status_code=200)
        mock_post.return_value.json.return_value = {"status": "REJECTED"}

        monolith = Monolith()
        result = monolith.create_order({"item": "mouse", "price": 0})

        self.assertEqual(result["payment_status"], "REJECTED")

if __name__ == "__main__":
    unittest.main()