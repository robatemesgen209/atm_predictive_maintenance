import sqlite3, os
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("ATM_DB_PATH", ROOT / "data" / "atm_maintenance.db"))

def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc, tb):
        try:
            return super().__exit__(exc_type, exc, tb)
        finally:
            self.close()

def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    with get_conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
          password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','manager','district')),
          district TEXT NOT NULL DEFAULT '', full_name TEXT NOT NULL DEFAULT '',
          is_active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS incidents(
          id INTEGER PRIMARY KEY AUTOINCREMENT, call_id TEXT, terminal_id TEXT NOT NULL,
          terminal_name TEXT NOT NULL DEFAULT '', problem TEXT NOT NULL, component TEXT NOT NULL,
          district TEXT NOT NULL, moti_district TEXT NOT NULL DEFAULT '',
          record_date TEXT, record_time TEXT, contact TEXT DEFAULT '', comment TEXT DEFAULT '',
          status TEXT NOT NULL DEFAULT 'new', solved_date TEXT DEFAULT '', solved_time TEXT DEFAULT '',
          source TEXT NOT NULL DEFAULT 'manual', created_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_inc_terminal ON incidents(terminal_id);
        CREATE INDEX IF NOT EXISTS idx_inc_district ON incidents(district);
        CREATE INDEX IF NOT EXISTS idx_inc_date ON incidents(record_date);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_call_id ON incidents(call_id)
          WHERE call_id IS NOT NULL AND call_id <> '';
        CREATE TABLE IF NOT EXISTS audit_log(
          id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT, detail TEXT, created_at TEXT);
        """)
        c.commit()

def audit(username, action, detail=""):
    with get_conn() as c:
        c.execute("INSERT INTO audit_log(username,action,detail,created_at) VALUES(?,?,?,?)",
                  (username, action, detail[:500], now_iso()))

def count_incidents():
    with get_conn() as c:
        return c.execute("SELECT COUNT(*) FROM incidents").fetchone()[0]

def load_incidents(district=None):
    q = "SELECT * FROM incidents"
    params = []
    if district:
        q += " WHERE district=?"; params.append(district)
    q += " ORDER BY COALESCE(record_date,'') DESC, id DESC"
    with get_conn() as c:
        return pd.read_sql_query(q, c, params=params)

def add_incident(data, username):
    from predictor import normalize_component
    component = normalize_component(data["problem"])
    with get_conn() as c:
        c.execute("""INSERT INTO incidents(call_id,terminal_id,terminal_name,problem,component,district,moti_district,
          record_date,record_time,contact,comment,status,solved_date,solved_time,source,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (data.get("call_id",""),data["terminal_id"].strip(),data.get("terminal_name",""),data["problem"],
           component,data["district"],data.get("moti_district",""),data.get("record_date",""),
           data.get("record_time",""),data.get("contact",""),data.get("comment",""),
           data.get("status","new"),data.get("solved_date",""),data.get("solved_time",""),
           "manual",now_iso()))
    audit(username,"incident_created",f'{data["terminal_id"]}: {data["problem"]}')

def import_dataframe(df, username):
    from predictor import normalize_component
    required = {"terminal_id","problem","district"}
    if not required.issubset(df.columns):
        raise ValueError("CSV must contain terminal_id, problem and district columns.")
    cols = ["call_id","terminal_id","terminal_name","problem","district","moti_district","record_date",
            "record_time","contact","comment","status","solved_date","solved_time"]
    df = df.copy()
    for col in cols:
        if col not in df: df[col] = ""
    df = df[cols].fillna("")
    # Idempotency: use call_id where available, otherwise a stable incident fingerprint.
    with get_conn() as c:
        existing_rows = c.execute("""SELECT call_id,terminal_id,problem,district,record_date,record_time
                                     FROM incidents""").fetchall()
    seen = set()
    for x in existing_rows:
        cid = str(x["call_id"] or "").strip()
        if cid:
            seen.add(("call",cid))
        else:
            seen.add(("fallback",str(x["terminal_id"]),str(x["problem"]),str(x["district"]),
                      str(x["record_date"]),str(x["record_time"])))
    rows = []
    for _,r in df.iterrows():
        terminal_id, problem, district_value = str(r.terminal_id).strip(), str(r.problem).strip(), str(r.district).strip()
        if not terminal_id or not district_value or not problem:
            continue
        call_id = str(r.call_id).strip()
        key = ("call",call_id) if call_id and call_id.lower()!="nan" else (
            "fallback",terminal_id,problem,district_value,str(r.record_date),str(r.record_time))
        if key in seen:
            continue
        seen.add(key)
        rows.append((call_id if call_id.lower()!="nan" else "",terminal_id,str(r.terminal_name),problem,
                     normalize_component(problem),district_value,str(r.moti_district),
                     str(r.record_date),str(r.record_time),str(r.contact),str(r.comment),
                     str(r.status or "new").lower(),str(r.solved_date),str(r.solved_time),"import",now_iso()))
    with get_conn() as c:
        c.executemany("""INSERT OR IGNORE INTO incidents(call_id,terminal_id,terminal_name,problem,component,district,moti_district,
          record_date,record_time,contact,comment,status,solved_date,solved_time,source,created_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
        imported = c.total_changes
    audit(username,"csv_import",f"Processed {len(df)} rows; inserted {imported}")
    return imported


def update_incident(incident_id, status, comment, username, district=None):
    with get_conn() as c:
        if district:
            cur = c.execute("UPDATE incidents SET status=?,comment=? WHERE id=? AND district=?",
                            (status,comment,incident_id,district))
        else:
            cur = c.execute("UPDATE incidents SET status=?,comment=? WHERE id=?",
                            (status,comment,incident_id))
        if cur.rowcount != 1:
            raise ValueError("Incident not found or outside your district permissions.")
    audit(username,"incident_updated",f"Incident {incident_id}: status={status}")

def seed_historical_data():
    # Import the supplied historical report exactly once into a fresh database.
    if count_incidents() == 0:
        seed_path = ROOT / "data" / "ncr_report.csv"
        if seed_path.exists():
            import_dataframe(pd.read_csv(seed_path, dtype={"terminal_id": str, "call_id": str}), "SYSTEM")
