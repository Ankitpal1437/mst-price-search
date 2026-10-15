import os,tempfile,unittest
fd,path=tempfile.mkstemp(suffix=".db");os.close(fd)
os.environ["DATABASE_URL"]="sqlite:///"+path
os.environ["APP_ENV"]="test";os.environ["SECRET_KEY"]="test-secret-long-enough-for-ci-123456789";os.environ["ADMIN_USERNAME"]="admin";os.environ["ADMIN_PASSWORD"]="test-password-123"
from fastapi.testclient import TestClient
from app.main import app
class ApiTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.c=TestClient(app);r=cls.c.post("/api/auth/login",json={"username":"admin","password":"test-password-123"});assert r.status_code==200,r.text;cls.h={"Authorization":"Bearer "+r.json()["access_token"]}
 def test_health(self):self.assertEqual(self.c.get("/api/health").status_code,200)
 def test_purchase_receipt_increases_stock(self):
  csv="CODE,DESCRIPTION,NRP,MRP,SOURCE\nPUR-001,Test basin,100,150,BATHROOM\n"
  self.c.post("/api/products/import",headers=self.h,files={"file":("p.csv",csv,"text/csv")})
  p=self.c.get("/api/products?q=PUR-001",headers=self.h).json()["items"][0]
  r=self.c.post("/api/purchases",headers=self.h,json={"supplier_name":"Supplier A","product_id":p["id"],"quantity":4,"unit_cost":50,"reference":"GRN-1"})
  self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()["new_stock"],4)
  self.assertEqual(self.c.get("/api/inventory",headers=self.h).json()["items"][0]["quantity"],4)
 def test_import_and_quote_total(self):
  csv="CODE,DESCRIPTION,NRP,MRP,SOURCE\nTEST-001,Test tap,100,150,FITTINGS\n"
  r=self.c.post("/api/products/import",headers=self.h,files={"file":("p.csv",csv,"text/csv")});self.assertEqual(r.status_code,200,r.text)
  q=self.c.post("/api/quotations",headers=self.h,json={"customer_name":"Test","discount_percent":10,"items":[{"code":"TEST-001","quantity":2,"price_mode":"NRP"}]});self.assertEqual(q.status_code,200,q.text);self.assertEqual(q.json()["total_amount"],180)
if __name__=="__main__":unittest.main()
