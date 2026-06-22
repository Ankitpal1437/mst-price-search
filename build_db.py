"""
build_db.py
Converts price.csv into an optimized SQLite database (mst.db).
Run this ONCE locally (or on deploy) whenever price.csv is updated.

Usage:
    python build_db.py
"""
import sqlite3
import csv
import os
import re

CSV_FILE = "price.csv"
DB_FILE = "mst.db"


def normalize(text):
    """Lowercase + strip, used for search columns."""
    return (text or "").strip().lower()


def build_database():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            code_norm TEXT NOT NULL,
            description TEXT,
            desc_norm TEXT,
            ewp TEXT,
            mdp TEXT,
            sdp TEXT,
            npp TEXT,
            nrp TEXT,
            mrp TEXT,
            old_nrp TEXT,
            old_mrp TEXT,
            source TEXT
        )
    """)

    rows_added = 0
    skipped = 0

    with open(CSV_FILE, newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        batch = []
        for row in reader:
            code = (row.get("CODE") or "").strip()
            desc = (row.get("DESCRIPTION") or "").strip()

            # Skip garbage / header-repeat / blank rows
            if not code or code.upper() == "CODE" or len(code) <= 2 or not desc:
                skipped += 1
                continue

            batch.append((
                code,
                normalize(code),
                desc,
                normalize(desc),
                (row.get("EWP") or "").strip(),
                (row.get("MDP") or "").strip(),
                (row.get("SDP") or "").strip(),
                (row.get("NPP") or "").strip(),
                (row.get("NRP") or "").strip(),
                (row.get("MRP") or "").strip(),
                (row.get("OLD_NRP") or "").strip(),
                (row.get("OLD_MRP") or "").strip(),
                (row.get("SOURCE") or "FITTINGS").strip().upper(),
            ))
            rows_added += 1

            if len(batch) >= 5000:
                cur.executemany("""
                    INSERT INTO products
                    (code, code_norm, description, desc_norm, ewp, mdp, sdp, npp, nrp, mrp, old_nrp, old_mrp, source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch)
                batch = []

        if batch:
            cur.executemany("""
                INSERT INTO products
                (code, code_norm, description, desc_norm, ewp, mdp, sdp, npp, nrp, mrp, old_nrp, old_mrp, source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)

    # Indexes for fast search (this is what makes search <1s on 70k+ rows)
    cur.execute("CREATE INDEX idx_code_norm ON products(code_norm)")
    cur.execute("CREATE INDEX idx_desc_norm ON products(desc_norm)")
    cur.execute("CREATE INDEX idx_source ON products(source)")

    conn.commit()
    conn.close()

    print(f"Database built: {DB_FILE}")
    print(f"Rows added: {rows_added}")
    print(f"Rows skipped (garbage): {skipped}")


if __name__ == "__main__":
    build_database()
