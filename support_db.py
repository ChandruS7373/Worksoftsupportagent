"""
Separate SQLite database for the Worksoft AI Support Agent.
File: worksoft_support.db
"""
import os
import re
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get(
    "SUPPORT_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "worksoft_support.db")
)


def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # ── Chat tables ───────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS support_sessions (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name  TEXT NOT NULL DEFAULT '',
            user_email TEXT NOT NULL DEFAULT '',
            status     TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")

    c.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL DEFAULT '',
            file_name  TEXT DEFAULT '',
            file_type  TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES support_sessions(id)
        )""")

    c.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id     INTEGER NOT NULL,
            user_name      TEXT NOT NULL DEFAULT '',
            user_email     TEXT NOT NULL DEFAULT '',
            issue_text     TEXT NOT NULL DEFAULT '',
            priority       TEXT NOT NULL DEFAULT 'High',
            sf_case_number TEXT DEFAULT '',
            sf_case_url    TEXT DEFAULT '',
            sf_error       TEXT DEFAULT '',
            email_sent     INTEGER NOT NULL DEFAULT 0,
            created_at     TEXT NOT NULL,
            FOREIGN KEY (session_id) REFERENCES support_sessions(id)
        )""")

    # ── Salesforce knowledge cache ────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS sf_knowledge (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            sf_case_id     TEXT UNIQUE NOT NULL,
            case_number    TEXT NOT NULL DEFAULT '',
            subject        TEXT NOT NULL DEFAULT '',
            description    TEXT DEFAULT '',
            status         TEXT DEFAULT '',
            resolution     TEXT DEFAULT '',
            comments       TEXT DEFAULT '',
            all_text       TEXT DEFAULT '',
            synced_at      TEXT NOT NULL
        )""")

    c.execute("""
        CREATE TABLE IF NOT EXISTS sf_sync_log (
            id         INTEGER PRIMARY KEY DEFAULT 1,
            last_sync  TEXT NOT NULL DEFAULT '',
            case_count INTEGER NOT NULL DEFAULT 0
        )""")

    # ── Indexes ───────────────────────────────────────────────
    c.execute("CREATE INDEX IF NOT EXISTS idx_msg_session ON support_messages(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_ticket_sess ON support_tickets(session_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sess_email  ON support_sessions(user_email)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_sfk_number  ON sf_knowledge(case_number)")

    conn.commit()
    conn.close()


# ── Session helpers ───────────────────────────────────────────
def create_session(user_name: str, user_email: str) -> int:
    now = datetime.now().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO support_sessions (user_name, user_email, status, created_at, updated_at) VALUES (?,?,?,?,?)",
        (user_name, user_email, "active", now, now),
    )
    sid = c.lastrowid
    conn.commit(); conn.close()
    return sid


def update_session_status(session_id: int, status: str):
    now = datetime.now().isoformat()
    conn = get_conn()
    conn.execute(
        "UPDATE support_sessions SET status=?, updated_at=? WHERE id=?",
        (status, now, session_id),
    )
    conn.commit(); conn.close()


def get_recent_sessions(limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM support_sessions ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Message helpers ───────────────────────────────────────────
def save_message(session_id: int, role: str, content: str,
                 file_name: str = "", file_type: str = ""):
    now = datetime.now().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO support_messages (session_id, role, content, file_name, file_type, created_at) VALUES (?,?,?,?,?,?)",
        (session_id, role, content, file_name, file_type, now),
    )
    conn.commit(); conn.close()


def get_messages(session_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM support_messages WHERE session_id=? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Ticket helpers ────────────────────────────────────────────
def save_ticket(session_id: int, user_name: str, user_email: str,
                issue_text: str, priority: str, sf_case_number: str = "",
                sf_case_url: str = "", sf_error: str = "", email_sent: bool = False) -> int:
    now = datetime.now().isoformat()
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """INSERT INTO support_tickets
           (session_id,user_name,user_email,issue_text,priority,
            sf_case_number,sf_case_url,sf_error,email_sent,created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (session_id, user_name, user_email, issue_text, priority,
         sf_case_number, sf_case_url, sf_error, int(email_sent), now),
    )
    tid = c.lastrowid
    conn.commit(); conn.close()
    return tid


def get_tickets(limit: int = 100) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM support_tickets ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── SF Knowledge sync ─────────────────────────────────────────
def upsert_sf_case(sf_case_id: str, case_number: str, subject: str,
                   description: str, status: str, resolution: str, comments: str):
    """Insert or update a cached Salesforce case."""
    all_text = " ".join([subject, description, resolution, comments]).lower()
    now = datetime.now().isoformat()
    conn = get_conn()
    conn.execute(
        """INSERT INTO sf_knowledge
           (sf_case_id, case_number, subject, description, status, resolution, comments, all_text, synced_at)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(sf_case_id) DO UPDATE SET
             case_number=excluded.case_number, subject=excluded.subject,
             description=excluded.description, status=excluded.status,
             resolution=excluded.resolution, comments=excluded.comments,
             all_text=excluded.all_text, synced_at=excluded.synced_at""",
        (sf_case_id, case_number, subject, description, status, resolution, comments, all_text, now),
    )
    conn.commit(); conn.close()


def delete_removed_cases(active_sf_ids: list) -> int:
    """Delete locally cached cases whose IDs are no longer in Salesforce."""
    if not active_sf_ids:
        return 0
    placeholders = ",".join("?" * len(active_sf_ids))
    conn = get_conn()
    cur = conn.execute(
        f"DELETE FROM sf_knowledge WHERE sf_case_id NOT IN ({placeholders})",
        active_sf_ids,
    )
    deleted = cur.rowcount
    conn.commit(); conn.close()
    return deleted


def update_sync_log(case_count: int):
    now = datetime.now().isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO sf_sync_log(id, last_sync, case_count) VALUES(1,?,?) "
        "ON CONFLICT(id) DO UPDATE SET last_sync=excluded.last_sync, case_count=excluded.case_count",
        (now, case_count),
    )
    conn.commit(); conn.close()


def get_sync_info() -> dict:
    conn = get_conn()
    row  = conn.execute("SELECT * FROM sf_sync_log WHERE id=1").fetchone()
    cnt  = conn.execute("SELECT COUNT(*) FROM sf_knowledge").fetchone()[0]
    conn.close()
    if row:
        return {"last_sync": row["last_sync"], "case_count": cnt}
    return {"last_sync": "", "case_count": cnt}


# ── Knowledge search ──────────────────────────────────────────
_STOP = {"the","a","an","is","it","in","on","at","to","and","or","of",
         "my","i","can","not","be","for","are","was","this","that",
         "with","from","have","has","do","did","get","got","how","why",
         "what","when","where","please","help","issue","problem","error"}


def search_knowledge(query: str = "", top_n: int = 3) -> list:
    """
    Search SF cases by matching keywords against comments + description + subject.
    Comments get highest weight; description is used as fallback when comments are empty.
    Returns top matching cases first.
    """
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM sf_knowledge "
        "WHERE (LENGTH(TRIM(comments)) > 10 "
        "   OR LENGTH(TRIM(description)) > 10 "
        "   OR LENGTH(TRIM(subject)) > 5) "
        "ORDER BY synced_at DESC LIMIT 500"
    ).fetchall()
    conn.close()

    if not rows:
        return []

    if not query.strip():
        return [dict(r) for r in rows[:top_n]]

    words = [w for w in re.findall(r"[a-z0-9]+", query.lower())
             if w not in _STOP and len(w) > 2]

    if not words:
        return [dict(r) for r in rows[:top_n]]

    def score(d: dict) -> int:
        comments = (d["comments"] or "").lower()
        desc     = (d["description"] or "").lower()
        subj     = (d["subject"] or "").lower()
        s = 0
        for w in words:
            s += comments.count(w) * 4
            s += desc.count(w) * 3
            s += subj.count(w) * 2
            for token in (comments + " " + desc).split():
                if len(w) >= 4 and len(token) >= 4:
                    if token.startswith(w[:4]) or w.startswith(token[:4]):
                        s += 1
        return s

    scored = sorted([dict(r) for r in rows], key=score, reverse=True)
    return [r for r in scored if score(r) > 0][:top_n]


def get_cases_with_comments(limit: int = 10) -> list:
    """Return most recent cases that have actual resolution data."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT * FROM sf_knowledge
           WHERE comments != '' OR description != ''
           ORDER BY synced_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_case_pool(limit: int = 150) -> list:
    """Return case subjects + first 300 chars of content for AI case selection."""
    conn = get_conn()
    rows = conn.execute(
        """SELECT sf_case_id, case_number, subject,
               SUBSTR(COALESCE(NULLIF(TRIM(comments),''), NULLIF(TRIM(description),''), ''), 1, 500) AS snippet
           FROM sf_knowledge ORDER BY synced_at DESC LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_case_subjects() -> list:
    """Return sf_case_id + subject for every cached case (for AI case identification)."""
    conn = get_conn()
    rows = conn.execute(
        "SELECT sf_case_id, case_number, subject FROM sf_knowledge ORDER BY synced_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cases_by_ids(sf_case_ids: list) -> list:
    """Fetch full case records (including comments/description) for given SF case IDs."""
    if not sf_case_ids:
        return []
    placeholders = ",".join("?" * len(sf_case_ids))
    conn = get_conn()
    rows = conn.execute(
        f"SELECT * FROM sf_knowledge WHERE sf_case_id IN ({placeholders})",
        sf_case_ids,
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── CSV import ───────────────────────────────────────────────
def import_csv_knowledge(csv_path: str) -> tuple:
    """
    Import Worksoft Support Queries CSV into sf_knowledge.
    Columns expected: CaseNum, Question/Problem, Error Message,
                      Root Cause, Resolution, Resolution Steps
    """
    import csv as _csv
    if not os.path.exists(csv_path):
        return 0, f"File not found: {csv_path}"
    imported, skipped = 0, 0
    try:
        enc = "utf-8-sig"
        for try_enc in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                open(csv_path, encoding=try_enc).read(512); enc = try_enc; break
            except Exception: pass
        with open(csv_path, newline="", encoding=enc) as f:
            reader = _csv.DictReader(f)
            for row in reader:
                case_num   = str(row.get("CaseNum",           "") or "").strip()
                subject    = str(row.get("Question/Problem",  "") or "").strip()
                error_msg  = str(row.get("Error Message",     "") or "").strip()
                root_cause = str(row.get("Root Cause",        "") or "").strip()
                resolution = str(row.get("Resolution",        "") or "").strip()
                res_steps  = str(row.get("Resolution Steps",  "") or "").strip()
                if not case_num:
                    skipped += 1
                    continue
                desc_parts = []
                if error_msg:  desc_parts.append(f"Error: {error_msg}")
                if root_cause: desc_parts.append(f"Root Cause: {root_cause}")
                upsert_sf_case(
                    sf_case_id  = f"CSV-{case_num}",
                    case_number = case_num,
                    subject     = subject,
                    description = "\n".join(desc_parts),
                    status      = "Closed",
                    resolution  = resolution,
                    comments    = res_steps,
                )
                imported += 1
    except Exception as exc:
        return imported, f"❌ Import error: {exc}"
    update_sync_log(imported)
    return imported, f"✅ Imported {imported} cases from CSV."


# ── Stats ─────────────────────────────────────────────────────
def get_stats() -> dict:
    conn = get_conn()
    c = conn.cursor()
    return {
        "total_sessions":     c.execute("SELECT COUNT(*) FROM support_sessions").fetchone()[0],
        "resolved":           c.execute("SELECT COUNT(*) FROM support_sessions WHERE status='resolved'").fetchone()[0],
        "escalated":          c.execute("SELECT COUNT(*) FROM support_sessions WHERE status='escalated'").fetchone()[0],
        "total_tickets":      c.execute("SELECT COUNT(*) FROM support_tickets").fetchone()[0],
        "sf_cases_cached":    c.execute("SELECT COUNT(*) FROM sf_knowledge").fetchone()[0],
    }
