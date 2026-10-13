# MST Ceramic World Showroom OS

Clean rebuild of the showroom web app. Frontend: React + Vite. Backend: FastAPI + SQLAlchemy. Local database: SQLite; production can use PostgreSQL via DATABASE_URL. Mobile and desktop responsive UI.

## Run backend
1. cd backend
2. python -m venv .venv and activate it
3. pip install -r requirements.txt
4. Copy .env.example to .env and change SECRET_KEY and ADMIN_PASSWORD
5. uvicorn app.main:app --reload

API docs are available at http://127.0.0.1:8000/docs

## Run frontend
1. cd frontend
2. npm install
3. npm run dev
4. Set VITE_API_URL if the backend is not on http://127.0.0.1:8000

The approved price CSV is retained at data/price.csv as an import source. Upload it using the Product Import endpoint in API docs. Verify the column mapping and all price/tax rules before creating customer-facing quotes.

Initial modules: login, dashboard, product search/import, customer CRM, inventory and stock movements, quotations, sales orders, follow-ups and visitor log. This is a first foundation, not yet production-certified. Configure secure secrets, backups, PostgreSQL and role permissions before live use.