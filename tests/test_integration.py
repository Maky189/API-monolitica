import unittest
import requests

BASE_URL = "http://localhost:5000"
AUTH_URL = "http://localhost:5000"  # gateway proxies auth, or use direct auth-service port


def get_token(username="admin", password="admin123"):
    resp = requests.post(
        f"http://localhost:5002/auth/token",
        json={"username": username, "password": password},
    )
    return resp.json().get("token")


class TestIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.token = get_token()
        cls.headers = {"Authorization": f"Bearer {cls.token}"}

    def test_full_flow(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Headset", "price": 200},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "APPROVED")

    def test_payment_rejected(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Headset", "price": 0},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payment_status"], "REJECTED")

    def test_missing_fields(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Teclado"},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_empty_body(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={},
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())

    def test_no_token_returns_401(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Teclado", "price": 100},
        )
        self.assertEqual(response.status_code, 401)
        self.assertIn("error", response.json())

    def test_invalid_token_returns_401(self):
        response = requests.post(
            f"{BASE_URL}/api/orders",
            json={"item": "Teclado", "price": 100},
            headers={"Authorization": "Bearer token-invalido"},
        )
        self.assertEqual(response.status_code, 401)

    def test_route_not_found(self):
        response = requests.get(f"{BASE_URL}/rota-inexistente")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_method_not_allowed(self):
        response = requests.get(f"{BASE_URL}/api/orders", headers=self.headers)
        self.assertEqual(response.status_code, 405)
        self.assertIn("error", response.json())

    def test_security_headers_present(self):
        response = requests.get(f"{BASE_URL}/healthz")
        self.assertIn("X-Content-Type-Options", response.headers)
        self.assertIn("X-Frame-Options", response.headers)
        self.assertIn("X-XSS-Protection", response.headers)
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")

    def test_auth_invalid_credentials(self):
        response = requests.post(
            "http://localhost:5002/auth/token",
            json={"username": "admin", "password": "errada"},
        )
        self.assertEqual(response.status_code, 401)

    def test_idempotency(self):
        import uuid
        key = str(uuid.uuid4())
        payload = {"item": "Mouse", "price": 150}
        r1 = requests.post(
            f"{BASE_URL}/api/orders",
            json=payload,
            headers={**self.headers, "Idempotency-Key": key},
        )
        r2 = requests.post(
            f"{BASE_URL}/api/orders",
            json=payload,
            headers={**self.headers, "Idempotency-Key": key},
        )
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r1.json()["order"]["id"], r2.json()["order"]["id"])


if __name__ == "__main__":
    unittest.main()
