import os
import sqlite3
from pathlib import Path
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras

DB_PATH = Path("data") / "app.db"

def _is_postgres():
    return bool(os.getenv("DATABASE_URL"))

def get_conn():
    """
    If DATABASE_URL exists => connect to Postgres (Render).
    Else => use SQLite (local dev).
    """
    if _is_postgres():
        db_url = os.getenv("DATABASE_URL")
        # Render often provides postgres://, psycopg2 expects it fine.
        conn = psycopg2.connect(db_url, sslmode="require")
        return conn
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

def _column_exists_sqlite(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return any(r["name"] == col for r in rows)

def _column_exists_pg(conn, table, col):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT 1
            FROM information_schema.columns
            WHERE table_name=%s AND column_name=%s
            LIMIT 1;
        """, (table, col))
        return cur.fetchone() is not None

def init_db():
    conn = get_conn()
    is_pg = _is_postgres()

    if is_pg:
        # ---------- Postgres ----------
        with conn.cursor() as cur:
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users(
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin','wash_tech')),
                full_name TEXT
            );
            """)

            cur.execute("""CREATE TABLE IF NOT EXISTS laundries(id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);""")
            cur.execute("""CREATE TABLE IF NOT EXISTS factories(id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);""")
            cur.execute("""CREATE TABLE IF NOT EXISTS departments(id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);""")
            cur.execute("""CREATE TABLE IF NOT EXISTS customers(id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);""")

            cur.execute("""CREATE TABLE IF NOT EXISTS wash_categories(id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);""")
            cur.execute("""CREATE TABLE IF NOT EXISTS wash_issues(id SERIAL PRIMARY KEY, name TEXT UNIQUE NOT NULL);""")

            cur.execute("""
            CREATE TABLE IF NOT EXISTS entries(
                id SERIAL PRIMARY KEY,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,

                customer_name TEXT,
                style_no TEXT,
                contract_no TEXT,

                customer_order_qty INTEGER,
                factory_order_qty INTEGER,
                total_shipment_qty INTEGER,
                wash_receive_qty INTEGER,
                wash_delivery_qty INTEGER,

                pcd_date TEXT,
                planned_pcd_date TEXT,
                actual_pcd_date TEXT,

                agreed_ex_factory TEXT,
                actual_ex_factory TEXT,

                wash_receive_date TEXT,
                wash_closing_date TEXT,

                shade_band_submission_date TEXT,
                shade_band_approval_date TEXT,

                factory_name TEXT,
                laundry_name TEXT,
                department_name TEXT,

                wash_category TEXT,

                subcontract_washing TEXT,

                issue_1 TEXT,
                issue_2 TEXT,
                issue_3 TEXT,
                other_issue_text TEXT,

                remarks TEXT,

                image_path TEXT
            );
            """)

        conn.commit()

        # seed admin if empty
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users;")
            c = cur.fetchone()[0]
            if c == 0:
                admin_pw = os.getenv("ADMIN_PASSWORD", "admin123")
                cur.execute("""
                    INSERT INTO users(username,password,role,full_name)
                    VALUES(%s,%s,%s,%s);
                """, ("admin", admin_pw, "admin", "Default Admin"))
        conn.commit()
        conn.close()
        return

    # ---------- SQLite ----------
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','wash_tech')),
        full_name TEXT
    );
    """)

    cur.execute("""CREATE TABLE IF NOT EXISTS laundries(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS factories(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")

    cur.execute("""CREATE TABLE IF NOT EXISTS wash_categories(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS wash_issues(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS entries(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL,
        created_by TEXT NOT NULL,

        customer_name TEXT,
        style_no TEXT,
        contract_no TEXT,

        customer_order_qty INTEGER,
        factory_order_qty INTEGER,
        total_shipment_qty INTEGER,
        wash_receive_qty INTEGER,
        wash_delivery_qty INTEGER,

        pcd_date TEXT,
        planned_pcd_date TEXT,
        actual_pcd_date TEXT,

        agreed_ex_factory TEXT,
        actual_ex_factory TEXT,

        wash_receive_date TEXT,
        wash_closing_date TEXT,

        shade_band_submission_date TEXT,
        shade_band_approval_date TEXT,

        factory_name TEXT,
        laundry_name TEXT,
        department_name TEXT,

        wash_category TEXT,

        subcontract_washing TEXT,

        issue_1 TEXT,
        issue_2 TEXT,
        issue_3 TEXT,
        other_issue_text TEXT,

        remarks TEXT,

        image_path TEXT
    );
    """)
    conn.commit()

    # seed admin
    cur.execute("SELECT COUNT(*) as c FROM users;")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO users(username,password,role,full_name) VALUES(?,?,?,?);",
            ("admin", os.getenv("ADMIN_PASSWORD", "admin123"), "admin", "Default Admin")
        )
        conn.commit()

    conn.close()

# ---------- CRUD helpers (work for both) ----------

def fetch_all(table_name):
    conn = get_conn()
    is_pg = _is_postgres()
    if is_pg:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(f"SELECT * FROM {table_name} ORDER BY name;")
            rows = cur.fetchall()
        conn.close()
        return rows
    else:
        rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY name;").fetchall()
        conn.close()
        return rows

def add_master(table_name, name):
    name = name.strip()
    if not name:
        return
    conn = get_conn()
    is_pg = _is_postgres()
    if is_pg:
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO {table_name}(name) VALUES(%s) ON CONFLICT (name) DO NOTHING;", (name,))
        conn.commit()
        conn.close()
    else:
        conn.execute(f"INSERT OR IGNORE INTO {table_name}(name) VALUES(?);", (name,))
        conn.commit()
        conn.close()

def delete_master(table_name, name):
    conn = get_conn()
    is_pg = _is_postgres()
    if is_pg:
        with conn.cursor() as cur:
            cur.execute(f"DELETE FROM {table_name} WHERE name=%s;", (name,))
        conn.commit()
        conn.close()
    else:
        conn.execute(f"DELETE FROM {table_name} WHERE name=?;", (name,))
        conn.commit()
        conn.close()

def add_wash_category(name):
    add_master("wash_categories", name)

def get_wash_categories():
    return fetch_all("wash_categories")

def validate_user(username, password):
    conn = get_conn()
    is_pg = _is_postgres()
    if is_pg:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT username, role, full_name FROM users
                WHERE username=%s AND password=%s;
            """, (username, password))
            row = cur.fetchone()
        conn.close()
        return row if row else None
    else:
        row = conn.execute("""
            SELECT username, role, full_name FROM users
            WHERE username=? AND password=?;
        """, (username, password)).fetchone()
        conn.close()
        return dict(row) if row else None

def create_user(username, password, role, full_name=None):
    username = username.strip()
    full_name = (full_name or "").strip()
    conn = get_conn()
    is_pg = _is_postgres()
    if is_pg:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users(username, password, role, full_name)
                VALUES(%s,%s,%s,%s);
            """, (username, password, role, full_name))
        conn.commit()
        conn.close()
    else:
        conn.execute("""
            INSERT INTO users(username, password, role, full_name)
            VALUES(?,?,?,?);
        """, (username, password, role, full_name))
        conn.commit()
        conn.close()

def save_entry(data: dict):
    conn = get_conn()
    is_pg = _is_postgres()

    keys = list(data.keys())
    vals = [data[k] for k in keys]

    if is_pg:
        placeholders = ",".join(["%s"] * len(keys))
        cols = ",".join(keys)
        with conn.cursor() as cur:
            cur.execute(f"INSERT INTO entries({cols}) VALUES({placeholders});", vals)
        conn.commit()
        conn.close()
    else:
        cols = ",".join(keys)
        qmarks = ",".join(["?"] * len(keys))
        conn.execute(f"INSERT INTO entries({cols}) VALUES({qmarks});", tuple(vals))
        conn.commit()
        conn.close()

def read_entries(date_from=None, date_to=None):
    conn = get_conn()
    is_pg = _is_postgres()

    where = []
    params = []
    if date_from:
        where.append("date(created_at) >= date(%s)" if is_pg else "date(created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(created_at) <= date(%s)" if is_pg else "date(created_at) <= date(?)")
        params.append(date_to)

    sql = "SELECT * FROM entries"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY created_at DESC;"

    if is_pg:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        conn.close()
        return rows
    else:
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
