# MST Ceramic World — Showroom OS

A clean, responsive showroom-management foundation for mobile and desktop.

## Modules
- Dashboard overview
- Searchable product catalogue and CSV price-list import
- Customer and project/site records
- Inventory stock-in, stock-out and balance adjustment
- Draft quotations with server-calculated totals
- Sales orders
- Follow-up tracker
- Showroom visitor register
- Role-aware sign-in (owner, manager, sales)

## Run locally
### Backend API
1. Open the `backend` folder.
2. Create and activate a Python virtual environment.
3. Run `pip install -r requirements.txt`.
4. Copy `.env.example` to `.env` and replace the example password and secret.
5. Run `uvicorn app.main:app --reload`.

### Frontend
1. Open the `frontend` folder.
2. Run `npm install`.
3. Copy `.env.example` to `.env`.
4. Run `npm run dev`.

API default: `http://127.0.0.1:8000`.

## Product CSV
The importer supports CODE, DESCRIPTION, SOURCE, EWP, MDP, SDP, NPP, NRP, MRP, OLD_NRP and OLD_MRP. Check brand/category mapping when those fields are absent from the source.

## Pricing caution
Quotation totals are estimates based on the chosen stored price field and discount. GST, freight, installation and customer-specific commercial terms are not calculated. Verify all amounts before issuing customer quotations.

## Before production
Use strong unique credentials, HTTPS, PostgreSQL, backups, and user acceptance tests. Review staff permissions, migration strategy, price/GST rules and stock workflows. Never commit `.env` or real customer data. This is a working MVP foundation, not yet production billing software.
