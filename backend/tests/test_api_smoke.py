import os
import unittest
from fastapi.testclient import TestClient

# CI supplies unique credentials and a fresh SQLite database before import.
from app.main import app, SessionLocal, Product

class ShowroomApiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        response = cls.client.post(
            "/api/auth/login",
            data={"username": os.getenv("ADMIN_USERNAME", "admin"),
                  "password": os.environ["ADMIN_PASSWORD"]},
        )
        if response.status_code != 200:
            raise RuntimeError("Test owner login failed: " + response.text)
        cls.token = response.json()["access_token"]
        with SessionLocal() as db:
            if not db.query(Product).filter_by(code="CI-SKU-001").first():
                db.add(Product(code="CI-SKU-001", description="CI test product",
                               brand="Test", category="Test", nrp=100, mrp=150))
                db.commit()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_quotation_total_is_calculated_on_server(self):
        response = self.client.post(
            "/api/quotations",
            headers={"Authorization": "Bearer " + self.token},
            json={"quote_number": "CI-QUOTE-001", "customer_name": "CI Customer",
                  "price_mode": "NRP", "discount_pct": 10,
                  "items": [{"product_code": "CI-SKU-001", "quantity": 2}],
                  "total_amount": 1},
        )
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["total_amount"], 180)
        self.assertEqual(payload["items"][0]["line_total"], 180)
        self.assertIn("Tax has not been calculated", payload["tax_note"])

    def test_quotation_rejects_empty_items(self):
        response = self.client.post(
            "/api/quotations",
            headers={"Authorization": "Bearer " + self.token},
            json={"quote_number": "CI-QUOTE-EMPTY", "customer_name": "CI Customer",
                  "price_mode": "NRP", "discount_pct": 0, "items": []},
        )
        self.assertEqual(response.status_code, 400)

if __name__ == "__main__":
    unittest.main()
