import sys
import os
import unittest
from unittest.mock import patch, Mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "order_service"))

os.environ.setdefault("INTERNAL_SERVICE_TOKEN", "test-token")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import app as order_app
from app import app as flask_app


class TestOrderService(unittest.TestCase):

    def setUp(self):
        flask_app.config["TESTING"] = True
        self.client = flask_app.test_client()
        self.internal_headers = {
            "X-Internal-Token": "test-token",
            "Content-Type": "application/json",
        }

    @patch("app._call_payment")
    def test_create_order_approved(self, mock_payment):
        mock_payment.return_value = {"status": "APPROVED", "instance": "payment-1"}

        response = self.client.post(
            "/orders",
            json={"item": "mouse", "price": 250},
            headers=self.internal_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["payment_status"], "APPROVED")
        self.assertEqual(data["order"]["item"], "mouse")

    @patch("app._call_payment")
    def test_create_order_rejected(self, mock_payment):
        mock_payment.return_value = {"status": "REJECTED", "instance": "payment-1"}

        response = self.client.post(
            "/orders",
            json={"item": "mouse", "price": 0},
            headers=self.internal_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["payment_status"], "REJECTED")

    @patch("app._call_payment")
    def test_order_fields_present(self, mock_payment):
        mock_payment.return_value = {"status": "APPROVED", "instance": "payment-1"}

        response = self.client.post(
            "/orders",
            json={"item": "teclado", "price": 300},
            headers=self.internal_headers,
        )
        data = response.get_json()
        self.assertIn("order", data)
        self.assertIn("payment_status", data)
        self.assertEqual(data["order"]["price"], 300)

    def test_missing_internal_token_returns_403(self):
        response = self.client.post(
            "/orders",
            json={"item": "mouse", "price": 100},
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 403)

    def test_wrong_internal_token_returns_403(self):
        response = self.client.post(
            "/orders",
            json={"item": "mouse", "price": 100},
            headers={"X-Internal-Token": "wrong", "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 403)

    @patch("app._call_payment")
    def test_payment_service_failure_returns_unknown(self, mock_payment):
        import requests as req
        mock_payment.side_effect = req.ConnectionError("down")

        response = self.client.post(
            "/orders",
            json={"item": "mouse", "price": 100},
            headers=self.internal_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["payment_status"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
