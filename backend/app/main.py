import os, csv, io, json
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime, date, timedelta
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Text, Float, DateTime, Date, func, or_
from sqlalchemy.orm import declarative_base, sessionmaker, Session

NAME=os.getenv('APP_NAME','MST Ceramic World'); SECRET=os.getenv('SECRET_KEY',''); DB_URL=os.getenv('DATABASE_URL','sqlite:///./mst_showroom.db')
if len(SECRET)<32 or SECRET=='replace-with-a-long-random-secret': raise RuntimeError('Set SECRET_KEY to a unique random value of at least 32 characters in backend/.env')
if os.getenv('ADMIN_PASSWORD','') in ('','change-this-password') or len(os.getenv('ADMIN_PASSWORD',''))<12: raise RuntimeError('Set ADMIN_PASSWORD to a unique password of at least 12 characters in backend/.env')
engine=create_engine(DB_URL,connect_args={'check_same_thread':False} if DB_URL.startswith('sqlite') else {},pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine,autoflush=False,autocommit=False); Base=declarative_base(); pwd=CryptContext(schemes=['bcrypt'],deprecated='auto'); oauth=OAuth2PasswordBearer(tokenUrl='/api/auth/login')
class User(Base):
 __tablename__='users'; id=Column(Integer,primary_key=True); username=Column(String(80),unique=True,index=True); password_hash=Column(String(255)); role=Column(String(30),default='sales'); active=Column(Integer,default=1)
class Product(Base):
 __tablename__='products'; id=Column(Integer,primary_key=True); code=Column(String(120),unique=True,index=True); description=Column(Text,default=''); brand=Column(String(80),default='Unspecified',index=True); category=Column(String(120),default='Uncategorised',index=True); source=Column(String(80),default=''); ewp=Column(Float,default=0); mdp=Column(Float,default=0); sdp=Column(Float,default=0); npp=Column(Float,default=0); nrp=Column(Float,default=0); mrp=Column(Float,default=0); old_nrp=Column(Float,default=0); old_mrp=Column(Float,default=0); gst_rate=Column(Float,default=0); active=Column(Integer,default=1)
class Customer(Base):
 __tablename__='customers'; id=Column(Integer,primary_key=True); name=Column(String(180),index=True); phone=Column(String(40),default=''); email=Column(String(180),default=''); site_name=Column(String(180),default=''); customer_type=Column(String(60),default='Retail'); address=Column(Text,default=''); notes=Column(Text,default=''); status=Column(String(40),default='New Inquiry'); created_at=Column(DateTime,default=datetime.utcnow)
class Inventory(Base):
 __tablename__='inventory'; id=Column(Integer,primary_key=True); product_code=Column(String(120),unique=True,index=True); product_name=Column(Text); brand=Column(String(80),default=''); category=Column(String(120),default='Uncategorised'); location=Column(String(120),default=''); quantity=Column(Float,default=0); reorder_level=Column(Float,default=0); updated_at=Column(DateTime,default=datetime.utcnow)
class Movement(Base):
 __tablename__='stock_movements'; id=Column(Integer,primary_key=True); product_code=Column(String(120),index=True); movement_type=Column(String(30)); quantity=Column(Float); reference=Column(String(180),default=''); created_at=Column(DateTime,default=datetime.utcnow)
class Order(Base):
 __tablename__='sales_orders'; id=Column(Integer,primary_key=True); order_number=Column(String(80),unique=True,index=True); customer_name=Column(String(180)); phone=Column(String(40),default=''); status=Column(String(40),default='Pending'); total_amount=Column(Float,default=0); expected_delivery=Column(Date); notes=Column(Text,default=''); created_at=Column(DateTime,default=datetime.utcnow)
class Quote(Base):
 __tablename__='quotations'; id=Column(Integer,primary_key=True); quote_number=Column(String(80),unique=True,index=True); customer_name=Column(String(180)); phone=Column(String(40),default=''); site_name=Column(String(180),default=''); price_mode=Column(String(40),default='NRP'); discount_pct=Column(Float,default=0); items_json=Column(Text,default='[]'); total_amount=Column(Float,default=0); status=Column(String(40),default='Draft'); created_at=Column(DateTime,default=datetime.utcnow)
class Followup(Base):
 __tablename__='followups'; id=Column(Integer,primary_key=True); customer_name=Column(String(180)); phone=Column(String(40),default=''); due_date=Column(Date); followup_type=Column(String(80),default='General'); notes=Column(Text,default=''); status=Column(String(30),default='Pending')
class Visitor(Base):
 __tablename__='visitors'; id=Column(Integer,primary_key=True); name=Column(String(180)); phone=Column(String(40),default=''); purpose=Column(String(100),default='Browsing'); visitor_type=Column(String(80),default='Walk-In'); check_in=Column(DateTime,default=datetime.utcnow); check_out=Column(DateTime)
Base.metadata.create_all(engine)
def migrate_product_columns():
 from sqlalchemy import inspect, text
 existing={col['name'] for col in inspect(engine).get_columns('products')}
 additions={'source':"VARCHAR(80) DEFAULT ''",'ewp':'FLOAT DEFAULT 0','mdp':'FLOAT DEFAULT 0','npp':'FLOAT DEFAULT 0','old_nrp':'FLOAT DEFAULT 0','old_mrp':'FLOAT DEFAULT 0'}
 with engine.begin() as conn:
  for name, definition in additions.items():
   if name not in existing: conn.execute(text(f'ALTER TABLE products ADD COLUMN {name} {definition}'))
migrate_product_columns()
def db_dep():
 d=SessionLocal()
 try: yield d
 finally: d.close()
def current_user(token:str=Depends(oauth),d:Session=Depends(db_dep)):
 try: name=jwt.decode(token,SECRET,algorithms=['HS256']).get('sub')
 except JWTError: raise HTTPException(401,'Invalid or expired token')
 u=d.query(User).filter_by(username=name,active=1).first()
 if not u: raise HTTPException(401,'User not found or inactive')
 return u
def roles(*allowed):
 def check(u:User=Depends(current_user)):
  if u.role not in allowed: raise HTTPException(403,'Permission denied')
  return u
 return check
def bootstrap():
 d=SessionLocal(); name=os.getenv('ADMIN_USERNAME','admin')
 if not d.query(User).filter_by(username=name).first(): d.add(User(username=name,password_hash=pwd.hash(os.environ['ADMIN_PASSWORD']),role='owner')); d.commit()
 d.close()
bootstrap(); app=FastAPI(title=NAME,version='0.1.0'); origins=[x.strip() for x in os.getenv('CORS_ORIGINS','http://localhost:5173').split(',') if x.strip()]; app.add_middleware(CORSMiddleware,allow_origins=origins,allow_credentials=True,allow_methods=['*'],allow_headers=['*'])
class CustomerIn(BaseModel): name:str=Field(min_length=1); phone:str=''; email:str=''; site_name:str=''; customer_type:str='Retail'; address:str=''; notes:str=''
class StockIn(BaseModel): product_code:str=Field(min_length=1); product_name:str=Field(min_length=1); brand:str=''; category:str='Uncategorised'; location:str=''; quantity:float=Field(ge=0,default=0); reorder_level:float=Field(ge=0,default=0)
class MoveIn(BaseModel): movement_type:str; quantity:float=Field(gt=0); reference:str=''
class OrderIn(BaseModel): order_number:str; customer_name:str; phone:str=''; status:str='Pending'; total_amount:float=Field(ge=0,default=0); expected_delivery:date|None=None; notes:str=''
class QuoteIn(BaseModel): quote_number:str; customer_name:str; phone:str=''; site_name:str=''; price_mode:str='NRP'; discount_pct:float=Field(ge=0,le=100,default=0); items:list[dict]=[]; total_amount:float=Field(ge=0,default=0)
class FollowIn(BaseModel): customer_name:str; phone:str=''; due_date:date; followup_type:str='General'; notes:str=''
class VisitorIn(BaseModel): name:str; phone:str=''; purpose:str='Browsing'; visitor_type:str='Walk-In'
@app.get('/api/health')
def health(): return {'ok':True,'app':NAME,'version':'0.1.0'}
@app.post('/api/auth/login')
def login(f:OAuth2PasswordRequestForm=Depends(),d:Session=Depends(db_dep)):
 u=d.query(User).filter_by(username=f.username,active=1).first()
 if not u or not pwd.verify(f.password,u.password_hash): raise HTTPException(401,'Incorrect username or password')
 return {'access_token':jwt.encode({'sub':u.username,'role':u.role,'exp':datetime.utcnow()+timedelta(hours=12)},SECRET,algorithm='HS256'),'token_type':'bearer','username':u.username,'role':u.role}
@app.get('/api/auth/me')
def me(u:User=Depends(current_user)): return {'username':u.username,'role':u.role}
@app.get('/api/dashboard')
def dashboard(d:Session=Depends(db_dep),u:User=Depends(current_user)):
 today=date.today(); return {'products':d.query(Product).filter_by(active=1).count(),'customers':d.query(Customer).count(),'quotations_open':d.query(Quote).filter(Quote.status.notin_(['Accepted','Rejected','Converted'])).count(),'followups_due':d.query(Followup).filter(Followup.status=='Pending',Followup.due_date<=today).count(),'visitors_today':d.query(Visitor).filter(func.date(Visitor.check_in)==today.isoformat()).count(),'inventory_items':d.query(Inventory).count(),'low_stock':d.query(Inventory).filter(Inventory.quantity<=Inventory.reorder_level).count(),'orders_open':d.query(Order).filter(Order.status.notin_(['Delivered','Cancelled'])).count()}
@app.get('/api/products')
def products(q:str='',limit:int=50,d:Session=Depends(db_dep),u:User=Depends(current_user)):
 x=d.query(Product).filter(Product.active==1)
 if q.strip(): t='%'+q.strip()+'%'; x=x.filter(or_(Product.code.ilike(t),Product.description.ilike(t),Product.brand.ilike(t),Product.category.ilike(t)))
 return {'items':[{'id':p.id,'code':p.code,'description':p.description,'brand':p.brand,'category':p.category,'source':p.source,'ewp':p.ewp,'mdp':p.mdp,'sdp':p.sdp,'npp':p.npp,'nrp':p.nrp,'mrp':p.mrp,'old_nrp':p.old_nrp,'old_mrp':p.old_mrp,'gst_rate':p.gst_rate} for p in x.order_by(Product.code).limit(min(max(limit,1),200)).all()]}
@app.post('/api/products/import')
def import_products(file:UploadFile=File(...),d:Session=Depends(db_dep),u:User=Depends(roles('owner','manager'))):
 raw=file.file.read()
 try: txt=raw.decode('utf-8-sig')
 except UnicodeDecodeError: txt=raw.decode('latin-1')
 reader=csv.DictReader(io.StringIO(txt)); headers={h.strip().lower():h for h in (reader.fieldnames or []) if h}
 existing_products={p.code:p for p in d.query(Product).all()}
 def pick(row,*keys,default=''):
  for k in keys:
   if headers.get(k) and row.get(headers[k]) not in (None,''): return row[headers[k]].strip()
  return default
 count=0
 for row in reader:
  code=pick(row,'item code','code','product code','sku','item_code').upper(); desc=pick(row,'description','product name','item description','name')
  if not code or not desc: continue
  def num(*keys):
   try:return float(pick(row,*keys,default='0').replace(',','').replace('₹','') or 0)
   except ValueError:return 0
  p=existing_products.get(code)
  if not p:
   p=Product(code=code);d.add(p);existing_products[code]=p
  p.description=desc;p.brand=pick(row,'brand',default='Unspecified') or 'Unspecified';p.source=pick(row,'source','product source','division');p.category=pick(row,'category','sub-category','sub category',default='Uncategorised') or 'Uncategorised';p.ewp=num('ewp');p.mdp=num('mdp');p.sdp=num('sdp');p.npp=num('npp');p.nrp=num('nrp');p.mrp=num('mrp');p.old_nrp=num('old_nrp','old nrp');p.old_mrp=num('old_mrp','old mrp');p.gst_rate=num('gst','gst rate','gst_rate');count+=1
 d.commit();return {'ok':True,'processed':count}
@app.get('/api/customers')
def customers(d:Session=Depends(db_dep),u:User=Depends(current_user)): return {'items':[{'id':x.id,'name':x.name,'phone':x.phone,'email':x.email,'site_name':x.site_name,'customer_type':x.customer_type,'status':x.status} for x in d.query(Customer).order_by(Customer.id.desc()).limit(500).all()]}
@app.post('/api/customers')
def add_customer(x:CustomerIn,d:Session=Depends(db_dep),u:User=Depends(current_user)):
 r=Customer(**x.model_dump());d.add(r);d.commit();d.refresh(r);return {'ok':True,'id':r.id}
@app.get('/api/inventory')
def inventory(d:Session=Depends(db_dep),u:User=Depends(current_user)): return {'items':[{'id':x.id,'product_code':x.product_code,'product_name':x.product_name,'brand':x.brand,'category':x.category,'location':x.location,'quantity':x.quantity,'reorder_level':x.reorder_level} for x in d.query(Inventory).order_by(Inventory.product_name).all()]}
@app.post('/api/inventory')
def add_inventory(x:StockIn,d:Session=Depends(db_dep),u:User=Depends(roles('owner','manager'))):
 if d.query(Inventory).filter_by(product_code=x.product_code).first():raise HTTPException(409,'Product code already exists')
 r=Inventory(**x.model_dump());d.add(r)
 if x.quantity:d.add(Movement(product_code=x.product_code,movement_type='Opening',quantity=x.quantity,reference='Opening stock'))
 d.commit();d.refresh(r);return {'ok':True,'id':r.id}
@app.post('/api/inventory/{item_id}/movements')
def move_stock(item_id:int,x:MoveIn,d:Session=Depends(db_dep),u:User=Depends(roles('owner','manager'))):
 r=d.query(Inventory).filter_by(id=item_id).first()
 if not r:raise HTTPException(404,'Inventory item not found')
 if x.movement_type not in ('in','out','adjustment'):raise HTTPException(400,'Movement must be in, out, or adjustment')
 qty=r.quantity+x.quantity if x.movement_type=='in' else r.quantity-x.quantity if x.movement_type=='out' else x.quantity
 if qty<0:raise HTTPException(400,'Stock cannot become negative')
 r.quantity=qty;d.add(Movement(product_code=r.product_code,movement_type=x.movement_type,quantity=x.quantity,reference=x.reference));d.commit();return {'ok':True,'quantity':qty}
@app.get('/api/orders')
def orders(d:Session=Depends(db_dep),u:User=Depends(current_user)):return {'items':[{'id':x.id,'order_number':x.order_number,'customer_name':x.customer_name,'phone':x.phone,'status':x.status,'total_amount':x.total_amount,'expected_delivery':x.expected_delivery.isoformat() if x.expected_delivery else None,'notes':x.notes} for x in d.query(Order).order_by(Order.id.desc()).limit(500).all()]}
@app.post('/api/orders')
def add_order(x:OrderIn,d:Session=Depends(db_dep),u:User=Depends(current_user)):
 if d.query(Order).filter_by(order_number=x.order_number).first():raise HTTPException(409,'Order number already exists')
 r=Order(**x.model_dump());d.add(r);d.commit();d.refresh(r);return {'ok':True,'id':r.id}
@app.patch('/api/orders/{oid}/status')
def order_status(oid:int,status_value:str,d:Session=Depends(db_dep),u:User=Depends(current_user)):
 if status_value not in ('Pending','Confirmed','In Progress','Ready for Delivery','Delivered','Cancelled'):raise HTTPException(400,'Invalid status')
 r=d.query(Order).filter_by(id=oid).first()
 if not r:raise HTTPException(404,'Order not found')
 r.status=status_value;d.commit();return {'ok':True}
@app.get('/api/quotations')
def quotations(d:Session=Depends(db_dep),u:User=Depends(current_user)):return {'items':[{'id':x.id,'quote_number':x.quote_number,'customer_name':x.customer_name,'phone':x.phone,'site_name':x.site_name,'price_mode':x.price_mode,'discount_pct':x.discount_pct,'items':json.loads(x.items_json or '[]'),'total_amount':x.total_amount,'status':x.status} for x in d.query(Quote).order_by(Quote.id.desc()).limit(500).all()]}
@app.post('/api/quotations')
def add_quote(x:QuoteIn,d:Session=Depends(db_dep),u:User=Depends(current_user)):
 if d.query(Quote).filter_by(quote_number=x.quote_number).first():raise HTTPException(409,'Quotation number already exists')
 r=Quote(quote_number=x.quote_number,customer_name=x.customer_name,phone=x.phone,site_name=x.site_name,price_mode=x.price_mode,discount_pct=x.discount_pct,items_json=json.dumps(x.items),total_amount=x.total_amount);d.add(r);d.commit();d.refresh(r);return {'ok':True,'id':r.id}
@app.get('/api/followups')
def followups(d:Session=Depends(db_dep),u:User=Depends(current_user)):return {'items':[{'id':x.id,'customer_name':x.customer_name,'phone':x.phone,'due_date':x.due_date.isoformat(),'followup_type':x.followup_type,'notes':x.notes,'status':x.status} for x in d.query(Followup).order_by(Followup.due_date).limit(500).all()]}
@app.post('/api/followups')
def add_followup(x:FollowIn,d:Session=Depends(db_dep),u:User=Depends(current_user)):r=Followup(**x.model_dump());d.add(r);d.commit();d.refresh(r);return {'ok':True,'id':r.id}
@app.patch('/api/followups/{fid}/complete')
def complete_followup(fid:int,d:Session=Depends(db_dep),u:User=Depends(current_user)):
 r=d.query(Followup).filter_by(id=fid).first()
 if not r:raise HTTPException(404,'Follow-up not found')
 r.status='Done';d.commit();return {'ok':True}
@app.get('/api/visitors')
def visitors(d:Session=Depends(db_dep),u:User=Depends(current_user)):return {'items':[{'id':x.id,'name':x.name,'phone':x.phone,'purpose':x.purpose,'visitor_type':x.visitor_type,'check_in':x.check_in.isoformat(),'check_out':x.check_out.isoformat() if x.check_out else None} for x in d.query(Visitor).order_by(Visitor.id.desc()).limit(300).all()]}
@app.post('/api/visitors')
def checkin(x:VisitorIn,d:Session=Depends(db_dep),u:User=Depends(current_user)):r=Visitor(**x.model_dump());d.add(r);d.commit();d.refresh(r);return {'ok':True,'id':r.id}
@app.post('/api/visitors/{vid}/checkout')
def checkout(vid:int,d:Session=Depends(db_dep),u:User=Depends(current_user)):
 r=d.query(Visitor).filter_by(id=vid).first()
 if not r:raise HTTPException(404,'Visitor not found')
 r.check_out=datetime.utcnow();d.commit();return {'ok':True}
