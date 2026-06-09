"""SQLite database operations for PvPI ADR Reporting Chatbot."""

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Optional

from config import DATA_DIR, DB_PATH

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('Doctor', 'Pharmacist', 'Admin')),
    name TEXT NOT NULL,
    email TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS adr_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_data TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    reporter_name TEXT NOT NULL,
    submitted_by TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id INTEGER,
    performed_by TEXT NOT NULL,
    details TEXT DEFAULT '{}',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_adr_reports_language ON adr_reports(language);
CREATE INDEX IF NOT EXISTS idx_adr_reports_created_at ON adr_reports(created_at);
CREATE INDEX IF NOT EXISTS idx_adr_reports_reporter_name ON adr_reports(reporter_name);
CREATE INDEX IF NOT EXISTS idx_adr_reports_submitted_by ON adr_reports(submitted_by);
"""


def get_connection() -> sqlite3.Connection:
    """Create a new SQLite connection."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict]:
    if row is None:
        return None
    return dict(row)


def test_connection() -> tuple[bool, str]:
    """Test database connectivity. Returns (success, message)."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1")
        conn.close()
        return True, "Connected"
    except Exception as e:
        return False, str(e)


@contextmanager
def get_db_cursor(commit: bool = False):
    """Context manager for database cursor with automatic cleanup."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


def init_database() -> None:
    """Initialize database tables if they do not exist."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        logger.info("Database initialized at %s", DB_PATH)
    except Exception as e:
        conn.rollback()
        logger.error("Database initialization failed: %s", e)
        raise
    finally:
        conn.close()


def create_user(
    username: str,
    password_hash: str,
    role: str,
    name: str,
    email: str = "",
) -> bool:
    """Insert a new user with parameterized query."""
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT OR IGNORE INTO users (username, password_hash, role, name, email, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, password_hash, role, name, email, datetime.utcnow().isoformat()),
            )
            return cur.rowcount > 0
    except Exception as e:
        logger.error("Failed to create user: %s", e)
        return False


def get_user_by_username(username: str) -> Optional[dict]:
    """Fetch user record by username."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, username, password_hash, role, name, email FROM users WHERE username = ?",
            (username,),
        )
        return _row_to_dict(cur.fetchone())


def get_all_users_credentials() -> dict:
    """Build credentials dict for streamlit-authenticator."""
    with get_db_cursor() as cur:
        cur.execute("SELECT username, password_hash, name, role, email FROM users")
        rows = cur.fetchall()

    credentials = {"usernames": {}}
    for row in rows:
        item = dict(row)
        credentials["usernames"][item["username"]] = {
            "name": item["name"],
            "password": item["password_hash"],
            "email": item.get("email") or f"{item['username']}@pvpi.local",
            "roles": [item["role"]],
        }
    return credentials


def save_adr_report(
    report_data: dict,
    language: str,
    reporter_name: str,
    submitted_by: str,
) -> Optional[int]:
    """Save ADR report and return the new report ID."""
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute(
                """
                INSERT INTO adr_reports (report_data, language, reporter_name, submitted_by, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    json.dumps(report_data),
                    language,
                    reporter_name,
                    submitted_by,
                    datetime.utcnow().isoformat(),
                ),
            )
            report_id = cur.lastrowid

            if report_id:
                log_audit(
                    cur,
                    action="CREATE",
                    entity_type="adr_report",
                    entity_id=report_id,
                    performed_by=submitted_by,
                    details={"language": language, "reporter_name": reporter_name},
                )
            return report_id
    except Exception as e:
        logger.error("Failed to save ADR report: %s", e)
        return None


def get_adr_report(report_id: int) -> Optional[dict]:
    """Fetch a single ADR report by ID."""
    with get_db_cursor() as cur:
        cur.execute("SELECT * FROM adr_reports WHERE id = ?", (report_id,))
        row = cur.fetchone()
        if row:
            result = dict(row)
            if isinstance(result.get("report_data"), str):
                result["report_data"] = json.loads(result["report_data"])
            return result
        return None


def get_all_adr_reports(
    search: str = "",
    language_filter: str = "",
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
) -> list[dict]:
    """Fetch all ADR reports with optional filters."""
    query = "SELECT * FROM adr_reports WHERE 1=1"
    params: list[Any] = []

    if search:
        query += (
            " AND (LOWER(reporter_name) LIKE LOWER(?) "
            "OR LOWER(report_data) LIKE LOWER(?) "
            "OR LOWER(submitted_by) LIKE LOWER(?))"
        )
        search_pattern = f"%{search}%"
        params.extend([search_pattern, search_pattern, search_pattern])

    if language_filter:
        query += " AND language = ?"
        params.append(language_filter)

    if date_from:
        query += " AND created_at >= ?"
        params.append(date_from.isoformat())

    if date_to:
        query += " AND created_at <= ?"
        params.append(date_to.isoformat())

    query += " ORDER BY created_at DESC"

    with get_db_cursor() as cur:
        cur.execute(query, params)
        rows = cur.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        if isinstance(item.get("report_data"), str):
            item["report_data"] = json.loads(item["report_data"])
        results.append(item)
    return results


def delete_adr_report(report_id: int, performed_by: str) -> bool:
    """Delete an ADR report by ID."""
    try:
        with get_db_cursor(commit=True) as cur:
            cur.execute("SELECT id FROM adr_reports WHERE id = ?", (report_id,))
            if not cur.fetchone():
                return False

            cur.execute("DELETE FROM adr_reports WHERE id = ?", (report_id,))
            log_audit(
                cur,
                action="DELETE",
                entity_type="adr_report",
                entity_id=report_id,
                performed_by=performed_by,
                details={"report_id": report_id},
            )
            return True
    except Exception as e:
        logger.error("Failed to delete ADR report: %s", e)
        return False


def get_report_stats() -> dict:
    """Get aggregate statistics for admin dashboard."""
    with get_db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS total FROM adr_reports")
        total = cur.fetchone()["total"]

        cur.execute(
            """
            SELECT language, COUNT(*) AS count
            FROM adr_reports
            GROUP BY language
            ORDER BY count DESC
            """
        )
        by_language = {row["language"]: row["count"] for row in cur.fetchall()}

        cur.execute(
            """
            SELECT DATE(created_at) AS report_date, COUNT(*) AS count
            FROM adr_reports
            GROUP BY DATE(created_at)
            ORDER BY report_date DESC
            LIMIT 30
            """
        )
        by_date = [
            {"date": str(row["report_date"]), "count": row["count"]}
            for row in cur.fetchall()
        ]

    return {"total": total, "by_language": by_language, "by_date": by_date}


def log_audit(
    cur,
    action: str,
    entity_type: str,
    entity_id: int,
    performed_by: str,
    details: Optional[dict] = None,
) -> None:
    """Insert an audit log entry using existing cursor."""
    cur.execute(
        """
        INSERT INTO audit_logs (action, entity_type, entity_id, performed_by, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            action,
            entity_type,
            entity_id,
            performed_by,
            json.dumps(details or {}),
            datetime.utcnow().isoformat(),
        ),
    )


def get_audit_logs(limit: int = 100) -> list[dict]:
    """Fetch recent audit logs."""
    with get_db_cursor() as cur:
        cur.execute(
            """
            SELECT * FROM audit_logs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()

    results = []
    for row in rows:
        item = dict(row)
        if isinstance(item.get("details"), str):
            item["details"] = json.loads(item["details"])
        results.append(item)
    return results
