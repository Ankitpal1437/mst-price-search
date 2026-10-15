import os,csv,io,json,time,secrets,hashlib,hmac,base64
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv
from fastapi import FastAPI,Depends,HTTPException,Header,UploadFile,File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel,Field
from sqlalchemy import create_engine,Column,Integer,String,Float,Boolean,DateTime,ForeignKey,Text
from sqlalchemy.orm import declarative_base,sessionmaker,Session
load_dotenv()
ENV=os.getenv("APP_ENV","development");KEY=os.getenv("SECRET_KEY","");ADMIN=os.getenv("ADMIN_USERNAME","admin");PASSWORD=os.getenv("ADMIN_PASSWORD","")
if ENV=="production" and (len(KEY)<32 or len(PASSWORD)<12):raise RuntimeError("Configure a long SECRET_KEY and ADMIN_PASSWORD.")
KEY=KEY or "local-dev-"+secrets.token_hex(24);PASSWORD=PASSWORD or "local-only-"+secrets.token_urlsafe(12)
URL=os.getenv("DATABASE_URL","sqlite:///./mst_showroom.db");engine=create_engine(URL,connect_args={"check_same_thread":False} if URL.startswith("sqlite") else {},pool_pre_ping=True);DB=sessionmaker(bind=engine,autoflush=False,autocommit=False);Base=declarative_base()
class User(Base):
 __tablename__="users";id=Column(Integer,primary_key=True);username=Column(String,unique=True);pw=Column(String);role=Column(String,default="sales");active=Column(Boolean,default=True)
class Product(Base):
 __tablename__="products";id=Column(Integer,primary_key=True);code=Column(String,unique=True,index=True);description=Column(Text,default="");brand=Column(String,default="Unspecified");category=Column(String,default="Uncategorised");source=Column(String,default="");ewp=Column(Float,default=0);mdp=Column(Float,default=0);sdp=Column(Float,default=0);npp=Column(Float,default=0);nrp=Column(Float,default=0);mrp=Column(Float,default=0);old_nrp=Column(Float,default=0);old_mrp=Column(Float,default=0);active=Column(Boolean,default=True)
class Customer(Base):
 __tablename__="customers";id=Column(Integer,primary_key=True);name=Column(String);phone=Column(String,default="");email=Column(String,default="");site_name=Column(String,default="");customer_type=Column(String,default="Retail");notes=Column(Text,default="")
class Inventory(Base):
 __tablename__="inventory";id=Column(Integer,primary_key=True);product_id=Column(Integer,ForeignKey("products.id"),unique=True);quantity=Column(Float,default=0);reorder_level=Column(Float,default=0);location=Column(String,default="")
class Move(Base):
 __tablename__="stock_movements";id=Column(Integer,primary_key=True);product_id=Column(Integer,ForeignKey("products.id"));kind=Column(String);quantity=Column(Float);balance=Column(Float);reference=Column(String,default="");user=Column(String,default="");created=Column(DateTime,default=datetime.utcnow)
class Quote(Base):
 __tablename__="quotations";id=Column(Integer,primary_key=True);number=Column(String,unique=True);customer=Column(String);status=Column(String,default="Draft");discount=Column(Float,default=0);total=Column(Float,default=0);notes=Column(Text,default="");lines=Column(Text,default="[]");created=Column(DateTime,default=datetime.utcnow)
class Order(Base):
 __tablename__="sales_orders";id=Column(Integer,primary_key=True);number=Column(String,unique=True);customer=Column(String);status=Column(String,default="Open");total=Column(Float,default=0);delivery=Column(String,default="");notes=Column(Text,default="")
class Purchase(Base):
 __tablename__="purchases";id=Column(Integer,primary_key=True);number=Column(String,unique=True);supplier=Column(String);product_id=Column(Integer,ForeignKey("products.id"));quantity=Column(Float);unit_cost=Column(Float,default=0);total=Column(Float,default=0);reference=Column(String,default="");notes=Column(Text,default="");created=Column(DateTime,default=datetime.utcnow)
class Followup(Base):
 __tablename__="followups";id=Column(Integer,primary_key=True);customer=Column(String);phone=Column(String,default="");due=Column(String,default="");purpose=Column(Text,default="");status=Column(String,default="Pending")
class Visitor(Base):
 __tablename__="visitors";id=Column(Integer,primary_key=True);name=Column(String);phone=Column(String,default="");purpose=Column(String,default="");entered=Column(DateTime,default=datetime.utcnow);exited=Column(DateTime,nullable=True)
Base.metadata.create_all(engine)
def hashpw(p,s=None):
 s=s or secrets.token_hex(16);return s+"$"+hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),210000).hex()
def checkpw(p,h):
 try:s,v=h.split("$",1);return hmac.compare_digest(hashlib.pbkdf2_hmac("sha256",p.encode(),s.encode(),210000).hex(),v)
 except Exception:return False
with DB() as d:
 if not d.query(User).filter_by(username=ADMIN).first():d.add(User(username=ADMIN,pw=hashpw(PASSWORD),role="owner"));d.commit()
def sign(u):
 b=base64.urlsafe_b64encode(json.dumps({"sub":u.username,"exp":int(time.time())+43200}).encode()).decode().rstrip("=");return b+"."+hmac.new(KEY.encode(),b.encode(),hashlib.sha256).hexdigest()
def unsign(t):
 try:
  b,s=t.split(".",1)
  if not hmac.compare_digest(s,hmac.new(KEY.encode(),b.encode(),hashlib.sha256).hexdigest()):return None
  x=json.loads(base64.urlsafe_b64decode(b+"="*(-len(b)%4)));return x if x["exp"]>=time.time() else None
 except Exception:return None
def dbdep():
 d=DB()
 try:yield d
 finally:d.close()
def userdep(authorization:Optional[str]=Header(None),d:Session=Depends(dbdep)):
 x=unsign(authorization.split(" ",1)[1]) if authorization and authorization.lower().startswith("bearer ") else None
 u=d.query(User).filter_by(username=(x or {}).get("sub"),active=True).first() if x else None
 if not u:raise HTTPException(401,"Sign in again.")
 return u
def role(*roles):
 def dep(u:User=Depends(userdep)):
  if u.role not in roles:raise HTTPException(403,"Permission denied.")
  return u
 return dep
app=FastAPI(title="MST Ceramic World Showroom OS")
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in os.getenv("CORS_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(",") if x.strip()],allow_methods=["*"],allow_headers=["*"])
class Login(BaseModel):username:str;password:str
class CustomerIn(BaseModel):name:str;phone:str="";email:str="";site_name:str="";customer_type:str="Retail";notes:str=""
class StockIn(BaseModel):movement_type:str;quantity:float=Field(ge=0);reference:str=""
class Line(BaseModel):code:str;quantity:float=Field(gt=0);price_mode:str="NRP"
class QuoteIn(BaseModel):customer_name:str;discount_percent:float=Field(default=0,ge=0,le=100);notes:str="";items:list[Line]=Field(min_length=1)
class OrderIn(BaseModel):customer_name:str;total_amount:float=Field(ge=0);expected_delivery:str="";notes:str=""
class PurchaseIn(BaseModel):supplier_name:str;product_id:int;quantity:float=Field(gt=0);unit_cost:float=Field(default=0,ge=0);reference:str="";notes:str=""
class FollowIn(BaseModel):customer_name:str;phone:str="";due_date:str="";purpose:str=""
class VisitorIn(BaseModel):name:str;phone:str="";purpose:str=""
def pjson(p):return {k:getattr(p,k) for k in ("id","code","description","brand","category","source","ewp","mdp","sdp","npp","nrp","mrp","old_nrp","old_mrp")}
@app.get("/api/health")
def health():return {"ok":True}
@app.post("/api/auth/login")
def login(x:Login,d:Session=Depends(dbdep)):
 u=d.query(User).filter_by(username=x.username,active=True).first()
 if not u or not checkpw(x.password,u.pw):raise HTTPException(401,"Invalid username or password.")
 return {"access_token":sign(u),"username":u.username,"role":u.role}
@app.get("/api/auth/me")
def me(u:User=Depends(userdep)):return {"username":u.username,"role":u.role}
@app.get("/api/dashboard")
def dashboard(d:Session=Depends(dbdep),u:User=Depends(userdep)):
 return {"products":d.query(Product).filter_by(active=True).count(),"customers":d.query(Customer).count(),"quotes":d.query(Quote).count(),"open_orders":d.query(Order).filter(Order.status!="Completed").count(),"pending_followups":d.query(Followup).filter_by(status="Pending").count(),"low_stock":d.query(Inventory).filter(Inventory.quantity<=Inventory.reorder_level).count(),"recent_quotes":[{"quote_no":q.number,"customer_name":q.customer,"total_amount":q.total,"status":q.status} for q in d.query(Quote).order_by(Quote.id.desc()).limit(5)]}
@app.get("/api/products")
def products(q:str="",limit:int=100,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 z=d.query(Product).filter_by(active=True)
 if q.strip():
  t="%"+q.strip()+"%";z=z.filter((Product.code.ilike(t))|(Product.description.ilike(t))|(Product.brand.ilike(t))|(Product.category.ilike(t)))
 a=z.order_by(Product.code).limit(max(1,min(limit,500))).all();return {"items":[pjson(p) for p in a],"count":len(a)}
@app.post("/api/products/import")
async def product_import(file:UploadFile=File(...),d:Session=Depends(dbdep),u:User=Depends(role("owner","manager"))):
 if not (file.filename or "").lower().endswith(".csv"):raise HTTPException(400,"Upload a CSV file.")
 raw=await file.read()
 if len(raw)>40*1024*1024:raise HTTPException(413,"CSV exceeds 40 MB.")
 try:
  rd=csv.DictReader(io.StringIO(raw.decode("utf-8-sig")));h={k.strip().upper():k for k in (rd.fieldnames or []) if k};ck=h.get("CODE") or h.get("ITEM CODE") or h.get("PRODUCT CODE")
  if not ck:raise HTTPException(400,"CSV must include CODE.")
  n=0
  for row in rd:
   code=(row.get(ck) or "").strip()
   if not code:continue
   def val(*ks):
    k=next((h[x] for x in ks if x in h),None);return (row.get(k) or "").strip() if k else ""
   def num(*ks):
    try:return max(0,float(val(*ks).replace(",","").replace("₹",""))) if val(*ks) else 0
    except ValueError:return 0
   p=d.query(Product).filter_by(code=code).first()
   if not p:p=Product(code=code);d.add(p)
   p.description=val("DESCRIPTION","PRODUCT DESCRIPTION","NAME") or p.description;p.source=val("SOURCE") or p.source;p.category=val("CATEGORY") or p.category or p.source or "Uncategorised";p.brand=val("BRAND") or p.brand or "Unspecified"
   for a,ks in {"ewp":("EWP",),"mdp":("MDP",),"sdp":("SDP",),"npp":("NPP",),"nrp":("NRP","NPP"),"mrp":("MRP",),"old_nrp":("OLD_NRP",),"old_mrp":("OLD_MRP",)}.items():
    v=num(*ks)
    if v or not getattr(p,a):setattr(p,a,v)
   n+=1
   if n%500==0:d.flush()
  d.commit();return {"processed":n}
 except HTTPException:d.rollback();raise
 except Exception as e:d.rollback();raise HTTPException(400,"CSV import error: "+str(e)[:120])
@app.get("/api/customers")
def customers(q:str="",d:Session=Depends(dbdep),u:User=Depends(userdep)):
 z=d.query(Customer)
 if q.strip():
  t="%"+q.strip()+"%";z=z.filter((Customer.name.ilike(t))|(Customer.phone.ilike(t))|(Customer.site_name.ilike(t)))
 return {"items":[{k:getattr(c,k) for k in ("id","name","phone","email","site_name","customer_type","notes")} for c in z.order_by(Customer.id.desc()).limit(500).all()]}
@app.post("/api/customers")
def add_customer(x:CustomerIn,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 c=Customer(**x.model_dump());d.add(c);d.commit();d.refresh(c);return {"id":c.id}
@app.get("/api/inventory")
def inventory(d:Session=Depends(dbdep),u:User=Depends(userdep)):
 return {"items":[{"id":i.id,"product_id":p.id,"code":p.code,"description":p.description,"brand":p.brand,"quantity":i.quantity,"reorder_level":i.reorder_level,"location":i.location} for i,p in d.query(Inventory,Product).join(Product,Product.id==Inventory.product_id).order_by(Product.code).limit(500).all()]}
@app.post("/api/inventory/{pid}/movements")
def movement(pid:int,x:StockIn,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 k=x.movement_type.lower()
 if k not in ("in","out","adjustment"):raise HTTPException(400,"Invalid stock movement.")
 if k!="adjustment" and x.quantity<=0:raise HTTPException(400,"Stock-in/out quantity must be positive.")
 p=d.query(Product).filter_by(id=pid,active=True).first()
 if not p:raise HTTPException(404,"Product not found.")
 i=d.query(Inventory).filter_by(product_id=pid).first()
 if not i:i=Inventory(product_id=pid,quantity=0,reorder_level=0,location="");d.add(i);d.flush()
 if k=="in":i.quantity+=x.quantity
 elif k=="out":
  if x.quantity>i.quantity:raise HTTPException(400,"Insufficient stock.")
  i.quantity-=x.quantity
 else:i.quantity=x.quantity
 d.add(Move(product_id=pid,kind=k,quantity=x.quantity,balance=i.quantity,reference=x.reference,user=u.username));d.commit();return {"quantity":i.quantity}
@app.get("/api/quotations")
def quotes(d:Session=Depends(dbdep),u:User=Depends(userdep)):
 return {"items":[{"id":q.id,"quote_no":q.number,"customer_name":q.customer,"status":q.status,"total_amount":q.total,"discount_percent":q.discount,"items":json.loads(q.lines or "[]"),"notes":q.notes} for q in d.query(Quote).order_by(Quote.id.desc()).limit(300).all()]}
@app.post("/api/quotations")
def add_quote(x:QuoteIn,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 fields={"EWP":"ewp","MDP":"mdp","SDP":"sdp","NPP":"npp","NRP":"nrp","MRP":"mrp"};lines=[];subtotal=0
 for l in x.items:
  p=d.query(Product).filter_by(code=l.code,active=True).first()
  if not p:raise HTTPException(400,"Unknown product: "+l.code)
  f=fields.get(l.price_mode.upper())
  if not f:raise HTTPException(400,"Invalid price field.")
  price=float(getattr(p,f) or 0)
  if price<=0:raise HTTPException(400,"No price for "+l.code)
  amount=round(price*l.quantity,2);subtotal+=amount;lines.append({"code":p.code,"description":p.description,"quantity":l.quantity,"price_mode":l.price_mode.upper(),"unit_price":price,"line_total":amount})
 total=round(subtotal*(1-x.discount_percent/100),2);num="Q-"+datetime.now().strftime("%y%m%d")+"-"+secrets.token_hex(3).upper();q=Quote(number=num,customer=x.customer_name,discount=x.discount_percent,total=total,notes=x.notes,lines=json.dumps(lines));d.add(q);d.commit();d.refresh(q);return {"id":q.id,"quote_no":num,"total_amount":total,"items":lines,"tax_calculated":False}
@app.get("/api/orders")
def orders(d:Session=Depends(dbdep),u:User=Depends(userdep)):
 return {"items":[{"id":o.id,"order_no":o.number,"customer_name":o.customer,"status":o.status,"total_amount":o.total,"expected_delivery":o.delivery} for o in d.query(Order).order_by(Order.id.desc()).limit(300).all()]}
@app.post("/api/orders")
def add_order(x:OrderIn,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 o=Order(number="SO-"+datetime.now().strftime("%y%m%d")+"-"+secrets.token_hex(3).upper(),customer=x.customer_name,total=x.total_amount,delivery=x.expected_delivery,notes=x.notes);d.add(o);d.commit();d.refresh(o);return {"id":o.id,"order_no":o.number}
@app.get("/api/purchases")
def purchases(d:Session=Depends(dbdep),u:User=Depends(userdep)):
 rows=d.query(Purchase,Product).join(Product,Product.id==Purchase.product_id).order_by(Purchase.id.desc()).limit(500).all()
 return {"items":[{"id":x.id,"purchase_no":x.number,"supplier_name":x.supplier,"code":p.code,"description":p.description,"quantity":x.quantity,"unit_cost":x.unit_cost,"total_amount":x.total,"reference":x.reference,"notes":x.notes,"created":x.created.isoformat()} for x,p in rows]}
@app.post("/api/purchases")
def add_purchase(x:PurchaseIn,d:Session=Depends(dbdep),u:User=Depends(role("owner","manager"))):
 p=d.query(Product).filter_by(id=x.product_id,active=True).first()
 if not p:raise HTTPException(404,"Product not found.")
 inv=d.query(Inventory).filter_by(product_id=p.id).first()
 if not inv:inv=Inventory(product_id=p.id,quantity=0,reorder_level=0,location="");d.add(inv);d.flush()
 total=round(x.quantity*x.unit_cost,2);number="PO-"+datetime.now().strftime("%y%m%d")+"-"+secrets.token_hex(3).upper()
 po=Purchase(number=number,supplier=x.supplier_name.strip(),product_id=p.id,quantity=x.quantity,unit_cost=x.unit_cost,total=total,reference=x.reference,notes=x.notes)
 inv.quantity+=x.quantity
 d.add(po);d.add(Move(product_id=p.id,kind="purchase",quantity=x.quantity,balance=inv.quantity,reference=x.reference or number,user=u.username));d.commit();d.refresh(po)
 return {"id":po.id,"purchase_no":number,"total_amount":total,"new_stock":inv.quantity}
@app.get("/api/followups")
def followups(d:Session=Depends(dbdep),u:User=Depends(userdep)):
 return {"items":[{"id":f.id,"customer_name":f.customer,"phone":f.phone,"due_date":f.due,"purpose":f.purpose,"status":f.status} for f in d.query(Followup).order_by(Followup.id.desc()).limit(300).all()]}
@app.post("/api/followups")
def add_follow(x:FollowIn,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 f=Followup(customer=x.customer_name,phone=x.phone,due=x.due_date,purpose=x.purpose);d.add(f);d.commit();d.refresh(f);return {"id":f.id}
@app.patch("/api/followups/{fid}/complete")
def complete(fid:int,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 f=d.query(Followup).filter_by(id=fid).first()
 if not f:raise HTTPException(404,"Follow-up not found.")
 f.status="Completed";d.commit();return {"id":fid}
@app.get("/api/visitors")
def visitors(d:Session=Depends(dbdep),u:User=Depends(userdep)):
 return {"items":[{"id":v.id,"name":v.name,"phone":v.phone,"purpose":v.purpose,"checked_in":v.entered.isoformat(),"checked_out":v.exited.isoformat() if v.exited else None} for v in d.query(Visitor).order_by(Visitor.id.desc()).limit(300).all()]}
@app.post("/api/visitors")
def checkin(x:VisitorIn,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 v=Visitor(name=x.name,phone=x.phone,purpose=x.purpose);d.add(v);d.commit();d.refresh(v);return {"id":v.id}
@app.patch("/api/visitors/{vid}/checkout")
def checkout(vid:int,d:Session=Depends(dbdep),u:User=Depends(userdep)):
 v=d.query(Visitor).filter_by(id=vid).first()
 if not v:raise HTTPException(404,"Visitor not found.")
 v.exited=datetime.utcnow();d.commit();return {"id":vid}
