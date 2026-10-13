"""
app.py
MST Ceramic World — Product Search + CRM
Flask backend. SQLite for product data (read-only, built from price.csv)
and for CRM data (customers, visitors, quotations, followups).
"""
import os
import sqlite3
import re
import json
from datetime import datetime, date
from flask import Flask, render_template, request, jsonify, g

APP_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_DB = os.path.join(APP_DIR, "mst.db")
CRM_DB = os.path.join(APP_DIR, "crm.db")

app = Flask(__name__)


# ---------------------------------------------------------------
# DB HELPERS
# ---------------------------------------------------------------
def get_products_db():
    if "products_db" not in g:
        g.products_db = sqlite3.connect(PRODUCTS_DB)
        g.products_db.row_factory = sqlite3.Row
    return g.products_db


def get_crm_db():
    if "crm_db" not in g:
        g.crm_db = sqlite3.connect(CRM_DB)
        g.crm_db.row_factory = sqlite3.Row
    return g.crm_db


@app.teardown_appcontext
def close_db(exception):
    pdb = g.pop("products_db", None)
    if pdb is not None:
        pdb.close()
    cdb = g.pop("crm_db", None)
    if cdb is not None:
        cdb.close()


def init_crm_db():
    """Create CRM tables if they don't exist yet."""
    conn = sqlite3.connect(CRM_DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            address TEXT,
            site_name TEXT,
            architect_name TEXT,
            notes TEXT,
            status TEXT DEFAULT 'New Inquiry',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS visitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            purpose TEXT,
            visitor_type TEXT,
            check_in TEXT,
            check_out TEXT,
            remarks TEXT,
            date TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS quotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            customer_phone TEXT,
            price_mode TEXT,
            discount_pct REAL,
            data_json TEXT,
            grand_total REAL,
            status TEXT DEFAULT 'Draft',
            created_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS followups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            phone TEXT,
            followup_date TEXT,
            type TEXT,
            notes TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------
# SEARCH LOGIC  (priority: exact > starts_with > contains > description)
# ---------------------------------------------------------------
def search_products(query, limit=40):
    q = query.strip().lower()
    if not q:
        return []

    db = get_products_db()

    # We pull a generous pool per bucket using indexed LIKE queries
    # (SQLite uses idx_code_norm / idx_desc_norm so this stays fast on 70k+ rows)
    exact = db.execute(
        "SELECT * FROM products WHERE code_norm = ? LIMIT ?", (q, limit)
    ).fetchall()

    starts = db.execute(
        "SELECT * FROM products WHERE code_norm LIKE ? AND code_norm != ? LIMIT ?",
        (q + "%", q, limit)
    ).fetchall()

    contains = db.execute(
        "SELECT * FROM products WHERE code_norm LIKE ? AND code_norm NOT LIKE ? LIMIT ?",
        ("%" + q + "%", q + "%", limit)
    ).fetchall()

    desc_match = db.execute(
        "SELECT * FROM products WHERE desc_norm LIKE ? AND code_norm NOT LIKE ? LIMIT ?",
        ("%" + q + "%", "%" + q + "%", limit)
    ).fetchall()

    # Merge, preserving priority order, de-duplicate by id
    seen = set()
    merged = []
    for bucket in (exact, starts, contains, desc_match):
        for row in bucket:
            if row["id"] not in seen:
                seen.add(row["id"])
                merged.append(row)

    return merged[:limit]


def row_to_dict(row):
    d = dict(row)
    return d


# ---------------------------------------------------------------
# PAGES
# ---------------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/crm")
def crm():
    return render_template("crm.html")


@app.route("/quotation")
def quotation_page():
    return render_template("quotation.html")


# ---------------------------------------------------------------
# API: PRODUCT SEARCH
# ---------------------------------------------------------------
@app.route("/api/search")
def api_search():
    query = request.args.get("q", "")
    if len(query.strip()) < 2:
        return jsonify({"results": [], "count": 0})

    results = search_products(query)
    data = [row_to_dict(r) for r in results]
    return jsonify({"results": data, "count": len(data)})


@app.route("/api/stats")
def api_stats():
    db = get_products_db()
    total = db.execute("SELECT COUNT(*) c FROM products").fetchone()["c"]
    fittings = db.execute("SELECT COUNT(*) c FROM products WHERE source='FITTINGS'").fetchone()["c"]
    lighting = db.execute("SELECT COUNT(*) c FROM products WHERE source='LIGHTING'").fetchone()["c"]
    return jsonify({"total": total, "fittings": fittings, "lighting": lighting})


# ---------------------------------------------------------------
# API: VISITORS / CHECK-IN
# ---------------------------------------------------------------
@app.route("/api/visitors", methods=["GET", "POST"])
def api_visitors():
    db = get_crm_db()
    if request.method == "POST":
        data = request.json
        now = datetime.now()
        db.execute("""
            INSERT INTO visitors (name, phone, purpose, visitor_type, check_in, date)
            VALUES (?,?,?,?,?,?)
        """, (
            data.get("name", ""), data.get("phone", ""), data.get("purpose", ""),
            data.get("visitor_type", "Walk-In"),
            now.strftime("%H:%M"), now.strftime("%Y-%m-%d")
        ))
        db.commit()
        return jsonify({"ok": True})

    today_str = date.today().strftime("%Y-%m-%d")
    rows = db.execute("SELECT * FROM visitors ORDER BY id DESC LIMIT 200").fetchall()
    visitors = [row_to_dict(r) for r in rows]
    today_count = sum(1 for v in visitors if v["date"] == today_str)
    pending = sum(1 for v in visitors if not v["check_out"])
    return jsonify({
        "visitors": visitors,
        "today_count": today_count,
        "total_count": len(visitors),
        "pending_count": pending
    })


@app.route("/api/visitors/<int:vid>/checkout", methods=["POST"])
def api_checkout(vid):
    db = get_crm_db()
    data = request.json or {}
    db.execute(
        "UPDATE visitors SET check_out = ?, remarks = ? WHERE id = ?",
        (datetime.now().strftime("%H:%M"), data.get("remarks", ""), vid)
    )
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# API: CUSTOMERS
# ---------------------------------------------------------------
@app.route("/api/customers", methods=["GET", "POST"])
def api_customers():
    db = get_crm_db()
    if request.method == "POST":
        data = request.json
        db.execute("""
            INSERT INTO customers (name, phone, address, site_name, architect_name, notes, status, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            data.get("name", ""), data.get("phone", ""), data.get("address", ""),
            data.get("site_name", ""), data.get("architect_name", ""),
            data.get("notes", ""), data.get("status", "New Inquiry"),
            datetime.now().isoformat()
        ))
        db.commit()
        return jsonify({"ok": True, "id": db.execute("SELECT last_insert_rowid() id").fetchone()["id"]})

    rows = db.execute("SELECT * FROM customers ORDER BY id DESC").fetchall()
    return jsonify({"customers": [row_to_dict(r) for r in rows]})


@app.route("/api/customers/<int:cid>", methods=["PUT"])
def api_update_customer(cid):
    db = get_crm_db()
    data = request.json
    db.execute("""
        UPDATE customers SET name=?, phone=?, address=?, site_name=?, architect_name=?, notes=?, status=?
        WHERE id=?
    """, (
        data.get("name", ""), data.get("phone", ""), data.get("address", ""),
        data.get("site_name", ""), data.get("architect_name", ""),
        data.get("notes", ""), data.get("status", "New Inquiry"), cid
    ))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# API: QUOTATIONS
# ---------------------------------------------------------------
@app.route("/api/quotations", methods=["GET", "POST"])
def api_quotations():
    db = get_crm_db()
    if request.method == "POST":
        data = request.json
        db.execute("""
            INSERT INTO quotations (customer_name, customer_phone, price_mode, discount_pct, data_json, grand_total, status, created_at)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            data.get("customer_name", ""), data.get("customer_phone", ""),
            data.get("price_mode", "nrp"), data.get("discount_pct", 0),
            json.dumps(data.get("bathrooms", [])), data.get("grand_total", 0),
            "Draft", datetime.now().isoformat()
        ))
        db.commit()
        qid = db.execute("SELECT last_insert_rowid() id").fetchone()["id"]
        return jsonify({"ok": True, "id": qid})

    rows = db.execute("SELECT * FROM quotations ORDER BY id DESC").fetchall()
    quotations = []
    for r in rows:
        d = row_to_dict(r)
        d["bathrooms"] = json.loads(d.pop("data_json") or "[]")
        quotations.append(d)
    return jsonify({"quotations": quotations})


@app.route("/api/quotations/<int:qid>/status", methods=["POST"])
def api_quotation_status(qid):
    db = get_crm_db()
    data = request.json
    db.execute("UPDATE quotations SET status=? WHERE id=?", (data.get("status", "Draft"), qid))
    db.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# API: FOLLOW-UPS
# ---------------------------------------------------------------
@app.route("/api/followups", methods=["GET", "POST"])
def api_followups():
    db = get_crm_db()
    if request.method == "POST":
        data = request.json
        db.execute("""
            INSERT INTO followups (customer_name, phone, followup_date, type, notes, status, created_at)
            VALUES (?,?,?,?,?,?,?)
        """, (
            data.get("customer_name", ""), data.get("phone", ""),
            data.get("followup_date", ""), data.get("type", "General"),
            data.get("notes", ""), "Pending", datetime.now().isoformat()
        ))
        db.commit()
        return jsonify({"ok": True})

    rows = db.execute("SELECT * FROM followups ORDER BY followup_date ASC").fetchall()
    return jsonify({"followups": [row_to_dict(r) for r in rows]})


@app.route("/api/followups/<int:fid>/status", methods=["POST"])
def api_followup_status(fid):
    db = get_crm_db()
    data = request.json
    db.execute("UPDATE followups SET status=? WHERE id=?", (data.get("status", "Done"), fid))
    db.commit()
    return jsonify({"ok": True})




# ---------------------------------------------------------------
# SHOWROOM OPERATIONS: DASHBOARD + INVENTORY + ORDERS
# ---------------------------------------------------------------
def init_operations_db():
    """Create operational tables without modifying the product catalogue DB."""
    conn = sqlite3.connect(CRM_DB)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS inventory_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL UNIQUE,
            product_name TEXT NOT NULL,
            brand TEXT DEFAULT '',
            category TEXT DEFAULT '',
            location TEXT DEFAULT '',
            quantity_on_hand REAL NOT NULL DEFAULT 0,
            reorder_level REAL NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_code TEXT NOT NULL,
            movement_type TEXT NOT NULL,
            quantity REAL NOT NULL,
            reference TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sales_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number TEXT NOT NULL UNIQUE,
            customer_name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'Pending',
            total_amount REAL NOT NULL DEFAULT 0,
            expected_delivery TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            po_number TEXT NOT NULL UNIQUE,
            supplier_name TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            total_amount REAL NOT NULL DEFAULT 0,
            expected_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory_items(category);
        CREATE INDEX IF NOT EXISTS idx_sales_orders_status ON sales_orders(status);
        CREATE INDEX IF NOT EXISTS idx_stock_movements_code ON stock_movements(product_code);
    """)
    conn.commit()
    conn.close()


@app.route("/dashboard")
def dashboard_page():
    return render_template("dashboard.html")


@app.route("/api/dashboard")
def api_dashboard():
    db = get_crm_db()
    today_str = date.today().strftime("%Y-%m-%d")
    summary = {}
    summary["customers"] = db.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
    summary["quotations"] = db.execute("SELECT COUNT(*) FROM quotations").fetchone()[0]
    summary["open_quotations"] = db.execute(
        "SELECT COUNT(*) FROM quotations WHERE status NOT IN ('Accepted','Rejected','Converted')"
    ).fetchone()[0]
    summary["followups_due"] = db.execute(
        "SELECT COUNT(*) FROM followups WHERE status='Pending' AND followup_date <= ?", (today_str,)
    ).fetchone()[0]
    summary["visitors_today"] = db.execute(
        "SELECT COUNT(*) FROM visitors WHERE date = ?", (today_str,)
    ).fetchone()[0]
    summary["inventory_items"] = db.execute("SELECT COUNT(*) FROM inventory_items").fetchone()[0]
    summary["low_stock"] = db.execute(
        "SELECT COUNT(*) FROM inventory_items WHERE quantity_on_hand <= reorder_level"
    ).fetchone()[0]
    summary["open_orders"] = db.execute(
        "SELECT COUNT(*) FROM sales_orders WHERE status NOT IN ('Delivered','Cancelled')"
    ).fetchone()[0]
    summary["pending_purchase_orders"] = db.execute(
        "SELECT COUNT(*) FROM purchase_orders WHERE status NOT IN ('Received','Cancelled')"
    ).fetchone()[0]
    summary["recent_quotations"] = [
        row_to_dict(r) for r in db.execute(
            "SELECT id, customer_name, customer_phone, grand_total, status, created_at "
            "FROM quotations ORDER BY id DESC LIMIT 5"
        ).fetchall()
    ]
    summary["due_followups"] = [
        row_to_dict(r) for r in db.execute(
            "SELECT id, customer_name, phone, followup_date, type, notes "
            "FROM followups WHERE status='Pending' AND followup_date <= ? "
            "ORDER BY followup_date ASC LIMIT 5", (today_str,)
        ).fetchall()
    ]
    return jsonify(summary)


@app.route("/api/inventory", methods=["GET", "POST"])
def api_inventory():
    db = get_crm_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        code = str(data.get("product_code", "")).strip()
        name = str(data.get("product_name", "")).strip()
        if not code or not name:
            return jsonify({"ok": False, "error": "Product code and product name are required."}), 400
        try:
            quantity = float(data.get("quantity_on_hand", 0))
            reorder = float(data.get("reorder_level", 0))
            if quantity < 0 or reorder < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Quantity and reorder level must be non-negative numbers."}), 400
        try:
            db.execute("""
                INSERT INTO inventory_items
                (product_code, product_name, brand, category, location, quantity_on_hand, reorder_level, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (code, name, str(data.get("brand", "")).strip(), str(data.get("category", "")).strip(),
                  str(data.get("location", "")).strip(), quantity, reorder, datetime.now().isoformat()))
            if quantity:
                db.execute("""
                    INSERT INTO stock_movements (product_code, movement_type, quantity, reference, notes, created_at)
                    VALUES (?, 'Opening Balance', ?, 'Opening stock', '', ?)
                """, (code, quantity, datetime.now().isoformat()))
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "This product code already exists in inventory."}), 409
        return jsonify({"ok": True}), 201

    rows = db.execute("SELECT * FROM inventory_items ORDER BY product_name COLLATE NOCASE").fetchall()
    return jsonify({"items": [row_to_dict(r) for r in rows], "count": len(rows)})


@app.route("/api/inventory/<int:item_id>/movement", methods=["POST"])
def api_inventory_movement(item_id):
    db = get_crm_db()
    data = request.get_json(silent=True) or {}
    movement_type = str(data.get("movement_type", "")).strip().lower()
    if movement_type not in ("in", "out", "adjustment"):
        return jsonify({"ok": False, "error": "Movement type must be in, out, or adjustment."}), 400
    try:
        quantity = float(data.get("quantity", 0))
        if quantity <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Quantity must be greater than zero."}), 400
    item = db.execute("SELECT * FROM inventory_items WHERE id=?", (item_id,)).fetchone()
    if not item:
        return jsonify({"ok": False, "error": "Inventory item not found."}), 404
    current = float(item["quantity_on_hand"])
    updated = current + quantity if movement_type == "in" else current - quantity if movement_type == "out" else quantity
    if updated < 0:
        return jsonify({"ok": False, "error": "Stock cannot become negative."}), 400
    now = datetime.now().isoformat()
    db.execute("UPDATE inventory_items SET quantity_on_hand=?, updated_at=? WHERE id=?", (updated, now, item_id))
    db.execute("""
        INSERT INTO stock_movements (product_code, movement_type, quantity, reference, notes, created_at)
        VALUES (?,?,?,?,?,?)
    """, (item["product_code"], movement_type.title(), quantity, str(data.get("reference", "")).strip(),
          str(data.get("notes", "")).strip(), now))
    db.commit()
    return jsonify({"ok": True, "quantity_on_hand": updated})


@app.route("/api/orders", methods=["GET", "POST"])
def api_orders():
    db = get_crm_db()
    if request.method == "POST":
        data = request.get_json(silent=True) or {}
        order_number = str(data.get("order_number", "")).strip()
        customer_name = str(data.get("customer_name", "")).strip()
        if not order_number or not customer_name:
            return jsonify({"ok": False, "error": "Order number and customer name are required."}), 400
        try:
            total = float(data.get("total_amount", 0))
            if total < 0:
                raise ValueError
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "Order total must be a non-negative number."}), 400
        try:
            db.execute("""
                INSERT INTO sales_orders
                (order_number, customer_name, phone, status, total_amount, expected_delivery, notes, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (order_number, customer_name, str(data.get("phone", "")).strip(),
                  str(data.get("status", "Pending")).strip(), total,
                  str(data.get("expected_delivery", "")).strip(), str(data.get("notes", "")).strip(),
                  datetime.now().isoformat()))
            db.commit()
        except sqlite3.IntegrityError:
            return jsonify({"ok": False, "error": "This order number already exists."}), 409
        return jsonify({"ok": True}), 201

    rows = db.execute("SELECT * FROM sales_orders ORDER BY id DESC").fetchall()
    return jsonify({"orders": [row_to_dict(r) for r in rows], "count": len(rows)})


@app.route("/api/orders/<int:order_id>/status", methods=["POST"])
def api_order_status(order_id):
    db = get_crm_db()
    data = request.get_json(silent=True) or {}
    status = str(data.get("status", "")).strip()
    allowed = {"Pending", "Confirmed", "In Progress", "Ready for Delivery", "Delivered", "Cancelled"}
    if status not in allowed:
        return jsonify({"ok": False, "error": "Invalid order status."}), 400
    cur = db.execute("UPDATE sales_orders SET status=? WHERE id=?", (status, order_id))
    db.commit()
    if not cur.rowcount:
        return jsonify({"ok": False, "error": "Order not found."}), 404
    return jsonify({"ok": True})


# ---------------------------------------------------------------
# STARTUP
# ---------------------------------------------------------------
init_crm_db()
init_operations_db()

if not os.path.exists(PRODUCTS_DB):
    print("WARNING: mst.db not found. Run build_db.py first!")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
