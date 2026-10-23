# MST Ceramic World — Showroom OS

Responsive showroom management for mobile and desktop. This branch is a safe rebuild proposal; `main` is not changed and `price.csv` is preserved.

## Modules
- Secure sign-in with owner/manager/sales role checks
- Dashboard metrics
- Product catalogue search and CSV price-list import
- Customer records
- Inventory, stock movements, low-stock visibility
- Quotations with server-calculated totals from the selected price field
- Sales orders
- Purchase receipts that automatically increase stock
- Customer follow-ups and visitor check-in/check-out

## Local development

### Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Set a unique `SECRET_KEY` (32+ characters) and strong `ADMIN_PASSWORD` in `.env` before deployment. Local-only defaults are not production credentials. The first owner account uses `ADMIN_USERNAME` and `ADMIN_PASSWORD`.

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Set `VITE_API_URL` in `frontend/.env` if the API is not at `http://127.0.0.1:8000`.

## Importing the price list
Sign in as owner/manager, then open Products → Import price list and upload a UTF-8 CSV with a `CODE` column. Supported pricing columns include EWP, MDP, SDP, NPP, NRP, MRP, OLD_NRP and OLD_MRP. Importing updates the product master; it does not automatically create physical stock.

## Pricing and stock notes
- Quote totals are recalculated on the server from product prices. Tax/GST is not calculated in this starter; confirm the correct business rule before issuing customer quotations.
- Purchase receipts add the received quantity to inventory and write a stock-movement record.
- Sales orders do not deduct stock automatically yet; this should be added after the showroom's order fulfilment process is confirmed.
- For PostgreSQL, set `DATABASE_URL`; SQLite is used by default.

## Security and release status
Do not publish dealer price lists, customer records, credentials, or production database files in a public repository. The repository's existing `price.csv` is preserved by this branch; because the repository is public, anyone with the URL may be able to access it. Review visibility and remove sensitive pricing only with an explicit decision. This branch is not deployed and should be tested before operational use.
