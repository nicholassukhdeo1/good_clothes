# cache.py — dead-simple SQLite cache keyed by brand.
# Brand research is slow + expensive and reused across every product of that brand,
# so cache hard. PRE-WARM this for your demo brand before you present (see README).
import sqlite3
import json

DB = "cache.db"


# this opens a SQLite connection to cache.db
def _conn():
    return sqlite3.connect(DB)

# creates the brands table, with brand as primary key
def init():
    with _conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS brands (brand TEXT PRIMARY KEY, payload TEXT)")


#this is just finding an equivalent key when checking new item
def get(brand: str):
    with _conn() as c:
        row = c.execute("SELECT payload FROM brands WHERE brand = ?", (brand.lower(),)).fetchone()
    return json.loads(row[0]) if row else None

# overwrites an existing key.
def put(brand: str, payload: dict):
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO brands (brand, payload) VALUES (?, ?)",
            (brand.lower(), json.dumps(payload)),
        )
