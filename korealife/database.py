"""SQLite persistence layer for KOREA-LIFE.

Two tables:
- profile   : a single-row onboarding profile (language, resident type, city...)
- reminders : the unified store for Life Manager reminders AND Life Plan tasks.
              Every actionable item (a manual reminder, a recurring bill, a
              document-expiry alert, or a task saved from an AI action plan) is
              a row here, so the Home dashboard and Life Manager share one
              source of truth.

The module intentionally keeps raw SQL small and explicit. Connections use
Row factory so callers get dict-like rows.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from . import config

_LOCK = threading.Lock()


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


@contextmanager
def _connect():
    """Yield a SQLite connection with sane defaults. Serialized via a lock so
    Streamlit's multiple script runs don't collide on writes."""
    conn = sqlite3.connect(config.database_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        with _LOCK:
            yield conn
            conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create tables if they do not yet exist. Safe to call on every app start."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                language TEXT NOT NULL DEFAULT 'en',
                resident_type TEXT,
                city TEXT,
                residence_category TEXT,
                important_dates TEXT,          -- JSON list of {label, date}
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'other',
                due_date TEXT NOT NULL,         -- YYYY-MM-DD
                amount REAL,                    -- optional monetary amount
                currency TEXT DEFAULT 'KRW',
                recurrence TEXT NOT NULL DEFAULT 'none',   -- none|weekly|monthly|yearly|custom
                recurrence_interval INTEGER,    -- for custom: number of days
                reminder_offsets TEXT,          -- JSON list of ints (days before)
                status TEXT NOT NULL DEFAULT 'upcoming',   -- upcoming|completed|dismissed
                notes TEXT,
                source_ref TEXT,                -- optional source/document reference
                source_ids TEXT,               -- JSON list of knowledge-base source ids
                created_from TEXT DEFAULT 'manual',        -- manual|ai
                is_statutory INTEGER NOT NULL DEFAULT 0,   -- verified statutory deadline?
                snoozed_until TEXT,             -- YYYY-MM-DD or NULL
                created_at TEXT,
                updated_at TEXT,
                completed_at TEXT
            );
            """
        )
        # ----- KOREA-LIFE CONNECT (institutional side) -----
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                org_type TEXT NOT NULL DEFAULT 'support',  -- university|employer|support
                city TEXT,
                description TEXT,
                contact_email TEXT,
                languages TEXT,                 -- JSON list
                verified INTEGER NOT NULL DEFAULT 0,       -- demo "verified" badge
                is_demo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS org_resources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                resource_type TEXT NOT NULL DEFAULT 'faq',  -- procedure|faq|requirement
                topic TEXT,                     -- JSON list of topic strings
                body TEXT,                      -- the verified content
                languages TEXT,                 -- JSON list
                status TEXT NOT NULL DEFAULT 'published',    -- published|draft
                is_demo INTEGER NOT NULL DEFAULT 1,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inquiries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                org_id INTEGER NOT NULL,
                requester_label TEXT,           -- coarse, no PII (e.g. "Resident · employee · Seoul")
                topic TEXT,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',   -- new|in_progress|resolved|closed
                response TEXT,
                source TEXT DEFAULT 'copilot',  -- copilot|manual
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT,
                updated_at TEXT,
                FOREIGN KEY (org_id) REFERENCES organizations(id) ON DELETE CASCADE
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS question_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic TEXT,                     -- coarse topic bucket only, never raw PII
                city TEXT,
                language TEXT,
                is_demo INTEGER NOT NULL DEFAULT 0,
                created_at TEXT
            );
            """
        )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
def get_profile() -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    if not row:
        return None
    data = dict(row)
    data["important_dates"] = json.loads(data.get("important_dates") or "[]")
    data["is_demo"] = bool(data.get("is_demo"))
    return data


def save_profile(
    *,
    language: str,
    resident_type: str,
    city: str,
    residence_category: str = "",
    important_dates: Optional[List[Dict[str, str]]] = None,
    is_demo: bool = False,
) -> None:
    important_dates = important_dates or []
    now = _now_iso()
    with _connect() as conn:
        existing = conn.execute("SELECT created_at FROM profile WHERE id = 1").fetchone()
        created_at = existing["created_at"] if existing else now
        conn.execute(
            """
            INSERT INTO profile (id, language, resident_type, city, residence_category,
                                 important_dates, is_demo, created_at, updated_at)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                language=excluded.language,
                resident_type=excluded.resident_type,
                city=excluded.city,
                residence_category=excluded.residence_category,
                important_dates=excluded.important_dates,
                is_demo=excluded.is_demo,
                updated_at=excluded.updated_at
            """,
            (
                language,
                resident_type,
                city,
                residence_category,
                json.dumps(important_dates, ensure_ascii=False),
                1 if is_demo else 0,
                created_at,
                now,
            ),
        )


def clear_profile() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM profile WHERE id = 1")


# ---------------------------------------------------------------------------
# Reminders / tasks
# ---------------------------------------------------------------------------
def _row_to_reminder(row: sqlite3.Row) -> Dict[str, Any]:
    data = dict(row)
    data["reminder_offsets"] = json.loads(data.get("reminder_offsets") or "[]")
    data["source_ids"] = json.loads(data.get("source_ids") or "[]")
    data["is_statutory"] = bool(data.get("is_statutory"))
    return data


def add_reminder(
    *,
    title: str,
    category: str,
    due_date: str,
    amount: Optional[float] = None,
    currency: str = "KRW",
    recurrence: str = "none",
    recurrence_interval: Optional[int] = None,
    reminder_offsets: Optional[List[int]] = None,
    notes: str = "",
    source_ref: str = "",
    source_ids: Optional[List[str]] = None,
    created_from: str = "manual",
    is_statutory: bool = False,
) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO reminders (title, category, due_date, amount, currency, recurrence,
                                   recurrence_interval, reminder_offsets, status, notes,
                                   source_ref, source_ids, created_from, is_statutory,
                                   created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'upcoming', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title.strip(),
                category,
                due_date,
                amount,
                currency,
                recurrence,
                recurrence_interval,
                json.dumps(reminder_offsets or []),
                notes.strip(),
                source_ref.strip(),
                json.dumps(source_ids or []),
                created_from,
                1 if is_statutory else 0,
                now,
                now,
            ),
        )
        return int(cur.lastrowid)


def get_reminder(reminder_id: int) -> Optional[Dict[str, Any]]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM reminders WHERE id = ?", (reminder_id,)).fetchone()
    return _row_to_reminder(row) if row else None


def list_reminders(include_completed: bool = True) -> List[Dict[str, Any]]:
    query = "SELECT * FROM reminders"
    if not include_completed:
        query += " WHERE status NOT IN ('completed', 'dismissed')"
    query += " ORDER BY due_date ASC, id ASC"
    with _connect() as conn:
        rows = conn.execute(query).fetchall()
    return [_row_to_reminder(r) for r in rows]


def update_reminder(reminder_id: int, **fields: Any) -> None:
    if not fields:
        return
    allowed = {
        "title", "category", "due_date", "amount", "currency", "recurrence",
        "recurrence_interval", "reminder_offsets", "status", "notes", "source_ref",
        "source_ids", "is_statutory", "snoozed_until", "completed_at",
    }
    sets: List[str] = []
    values: List[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        if key in ("reminder_offsets", "source_ids"):
            value = json.dumps(value or [])
        if key == "is_statutory":
            value = 1 if value else 0
        sets.append(f"{key} = ?")
        values.append(value)
    if not sets:
        return
    sets.append("updated_at = ?")
    values.append(_now_iso())
    values.append(reminder_id)
    with _connect() as conn:
        conn.execute(f"UPDATE reminders SET {', '.join(sets)} WHERE id = ?", values)


def delete_reminder(reminder_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM reminders WHERE id = ?", (reminder_id,))


def delete_all_reminders() -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM reminders")


def count_reminders() -> int:
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM reminders").fetchone()["c"])


# ===========================================================================
# KOREA-LIFE CONNECT data access (organizations, resources, inquiries, trends)
# ===========================================================================
def _jload(value, default):
    try:
        return json.loads(value) if value else default
    except (ValueError, TypeError):
        return default


# ----- Organizations -----
def add_organization(*, name, org_type, city="", description="", contact_email="",
                     languages=None, verified=False, is_demo=True) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO organizations (name, org_type, city, description, contact_email,
                   languages, verified, is_demo, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name.strip(), org_type, city, description, contact_email,
             json.dumps(languages or []), 1 if verified else 0, 1 if is_demo else 0, now, now),
        )
        return int(cur.lastrowid)


def _row_to_org(row):
    d = dict(row)
    d["languages"] = _jload(d.get("languages"), [])
    d["verified"] = bool(d.get("verified"))
    d["is_demo"] = bool(d.get("is_demo"))
    return d


def list_organizations():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM organizations ORDER BY name ASC").fetchall()
    return [_row_to_org(r) for r in rows]


def get_organization(org_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    return _row_to_org(row) if row else None


def update_organization(org_id, **fields):
    allowed = {"name", "org_type", "city", "description", "contact_email", "languages", "verified"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k == "languages":
            v = json.dumps(v or [])
        if k == "verified":
            v = 1 if v else 0
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(_now_iso())
    vals.append(org_id)
    with _connect() as conn:
        conn.execute(f"UPDATE organizations SET {', '.join(sets)} WHERE id = ?", vals)


def count_organizations():
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM organizations").fetchone()["c"])


# ----- Org resources -----
def add_org_resource(*, org_id, title, resource_type="faq", topic=None, body="",
                     languages=None, status="published", is_demo=True) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO org_resources (org_id, title, resource_type, topic, body,
                   languages, status, is_demo, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (org_id, title.strip(), resource_type, json.dumps(topic or []), body,
             json.dumps(languages or []), status, 1 if is_demo else 0, now, now),
        )
        return int(cur.lastrowid)


def _row_to_resource(row):
    d = dict(row)
    d["topic"] = _jload(d.get("topic"), [])
    d["languages"] = _jload(d.get("languages"), [])
    d["is_demo"] = bool(d.get("is_demo"))
    return d


def list_org_resources(org_id=None, only_published=False):
    q = "SELECT * FROM org_resources"
    conds, params = [], []
    if org_id is not None:
        conds.append("org_id = ?")
        params.append(org_id)
    if only_published:
        conds.append("status = 'published'")
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY updated_at DESC"
    with _connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return [_row_to_resource(r) for r in rows]


def get_org_resource(res_id):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM org_resources WHERE id = ?", (res_id,)).fetchone()
    return _row_to_resource(row) if row else None


def update_org_resource(res_id, **fields):
    allowed = {"title", "resource_type", "topic", "body", "languages", "status"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        if k in ("topic", "languages"):
            v = json.dumps(v or [])
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(_now_iso())
    vals.append(res_id)
    with _connect() as conn:
        conn.execute(f"UPDATE org_resources SET {', '.join(sets)} WHERE id = ?", vals)


def delete_org_resource(res_id):
    with _connect() as conn:
        conn.execute("DELETE FROM org_resources WHERE id = ?", (res_id,))


# ----- Inquiries -----
def add_inquiry(*, org_id, message, requester_label="", topic="", status="new",
                source="copilot", is_demo=False) -> int:
    now = _now_iso()
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO inquiries (org_id, requester_label, topic, message, status,
                   source, is_demo, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (org_id, requester_label, topic, message.strip(), status, source,
             1 if is_demo else 0, now, now),
        )
        return int(cur.lastrowid)


def _row_to_inquiry(row):
    d = dict(row)
    d["is_demo"] = bool(d.get("is_demo"))
    return d


def list_inquiries(org_id=None, status=None):
    q = "SELECT * FROM inquiries"
    conds, params = [], []
    if org_id is not None:
        conds.append("org_id = ?")
        params.append(org_id)
    if status:
        conds.append("status = ?")
        params.append(status)
    if conds:
        q += " WHERE " + " AND ".join(conds)
    q += " ORDER BY created_at DESC"
    with _connect() as conn:
        rows = conn.execute(q, params).fetchall()
    return [_row_to_inquiry(r) for r in rows]


def update_inquiry(inq_id, **fields):
    allowed = {"status", "response", "topic"}
    sets, vals = [], []
    for k, v in fields.items():
        if k not in allowed:
            continue
        sets.append(f"{k} = ?")
        vals.append(v)
    if not sets:
        return
    sets.append("updated_at = ?")
    vals.append(_now_iso())
    vals.append(inq_id)
    with _connect() as conn:
        conn.execute(f"UPDATE inquiries SET {', '.join(sets)} WHERE id = ?", vals)


# ----- Question log (anonymized trends) -----
def log_question(*, topic, city="", language="", is_demo=False, created_at=None):
    with _connect() as conn:
        conn.execute(
            "INSERT INTO question_log (topic, city, language, is_demo, created_at) VALUES (?, ?, ?, ?, ?)",
            (topic, city, language, 1 if is_demo else 0, created_at or _now_iso()),
        )


def list_question_log():
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM question_log ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def count_question_log():
    with _connect() as conn:
        return int(conn.execute("SELECT COUNT(*) AS c FROM question_log").fetchone()["c"])
