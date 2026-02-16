import sqlite3
from pathlib import Path

DB_PATH = Path("data") / "app.db"

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH.as_posix(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def _column_exists(conn, table, col):
    rows = conn.execute(f"PRAGMA table_info({table});").fetchall()
    return any(r["name"] == col for r in rows)

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    # USERS
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('admin','wash_tech')),
        full_name TEXT
    );
    """)

    # MASTERS
    cur.execute("""CREATE TABLE IF NOT EXISTS laundries(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS factories(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS departments(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")
    cur.execute("""CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")

    # WASH CATEGORY
    cur.execute("""CREATE TABLE IF NOT EXISTS wash_categories(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")

    # WASH ISSUES
    cur.execute("""CREATE TABLE IF NOT EXISTS wash_issues(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);""")

    # MAIN ENTRIES TABLE (Create once; later we add columns safely)
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

        -- keep these columns for compatibility
        pcd_date TEXT,                -- (we won't use in UI)
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

        issue_1 TEXT,
        issue_2 TEXT,
        issue_3 TEXT,
        other_issue_text TEXT,

        remarks TEXT,

        image_path TEXT
    );
    """)
    conn.commit()

    # MIGRATIONS (in case old DB exists without new columns)
    add_cols = [
        ("entries", "customer_name", "TEXT"),
        ("entries", "planned_pcd_date", "TEXT"),
        ("entries", "actual_pcd_date", "TEXT"),
        ("entries", "agreed_ex_factory", "TEXT"),
        ("entries", "actual_ex_factory", "TEXT"),
        ("entries", "wash_receive_date", "TEXT"),
        ("entries", "wash_closing_date", "TEXT"),
        ("entries", "shade_band_submission_date", "TEXT"),
        ("entries", "shade_band_approval_date", "TEXT"),
        ("entries", "remarks", "TEXT"),
        ("entries", "wash_category", "TEXT"),
        ("entries", "image_path", "TEXT"),
        ("entries", "subcontract_washing", "TEXT"),
        ("entries", "issue_1", "TEXT"),
        ("entries", "issue_2", "TEXT"),
        ("entries", "issue_3", "TEXT"),
        ("entries", "other_issue_text", "TEXT"),
    ]
    for table, col, ctype in add_cols:
        if not _column_exists(conn, table, col):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ctype};")
    conn.commit()

    # SEED DEFAULT ADMIN
    cur.execute("SELECT COUNT(*) AS c FROM users;")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO users(username,password,role,full_name) VALUES(?,?,?,?);",
            ("admin", "admin123", "admin", "Default Admin")
        )
        conn.commit()

    conn.close()

def fetch_all(table_name):
    conn = get_conn()
    rows = conn.execute(f"SELECT * FROM {table_name} ORDER BY name;").fetchall()
    conn.close()
    return rows

def add_master(table_name, name):
    conn = get_conn()
    conn.execute(f"INSERT OR IGNORE INTO {table_name}(name) VALUES(?);", (name.strip(),))
    conn.commit()
    conn.close()

def delete_master(table_name, name):
    conn = get_conn()
    conn.execute(f"DELETE FROM {table_name} WHERE name=?;", (name,))
    conn.commit()
    conn.close()

def add_wash_category(name):
    conn = get_conn()
    conn.execute("INSERT OR IGNORE INTO wash_categories(name) VALUES(?);", (name.strip(),))
    conn.commit()
    conn.close()

def get_wash_categories():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM wash_categories ORDER BY name;").fetchall()
    conn.close()
    return rows

def validate_user(username, password):
    conn = get_conn()
    row = conn.execute("""
        SELECT username, role, full_name FROM users
        WHERE username=? AND password=?;
    """, (username, password)).fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(username, password, role, full_name=None):
    conn = get_conn()
    conn.execute("""
        INSERT INTO users(username, password, role, full_name)
        VALUES(?,?,?,?);
    """, (username.strip(), password, role, (full_name or "").strip()))
    conn.commit()
    conn.close()

def save_entry(data: dict):
    conn = get_conn()
    keys = ",".join(data.keys())
    qmarks = ",".join(["?"] * len(data))
    conn.execute(f"INSERT INTO entries({keys}) VALUES({qmarks});", tuple(data.values()))
    conn.commit()
    conn.close()

def read_entries(date_from=None, date_to=None):
    conn = get_conn()
    base = "SELECT * FROM entries"
    params = []
    where = []
    if date_from:
        where.append("date(created_at) >= date(?)")
        params.append(date_from)
    if date_to:
        where.append("date(created_at) <= date(?)")
        params.append(date_to)
    if where:
        base += " WHERE " + " AND ".join(where)
    base += " ORDER BY created_at DESC;"
    rows = conn.execute(base, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
