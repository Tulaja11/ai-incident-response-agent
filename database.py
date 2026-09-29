"""Plain sqlite3 — one table, four functions, ~60 lines.

No ORM. Interview answer: "There's one table. SQLAlchemy would add
a dependency and an abstraction layer for zero benefit at this scale."
"""

import sqlite3
import os
import json

DB_PATH = os.getenv("DB_PATH", "incidents.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    # Drop and recreate — fresh start on every deploy/restart
    conn.execute("DROP TABLE IF EXISTS incidents")
    conn.execute("""
        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT DEFAULT (datetime('now')),
            raw_log TEXT NOT NULL,
            error_type TEXT,
            affected_system TEXT,
            severity TEXT,
            severity_confidence REAL,
            report TEXT,
            processing_time REAL
        )
    """)
    conn.commit()
    conn.close()


def insert_incident(raw_log, error_type, affected_system, severity,
                    severity_confidence, report, processing_time):
    conn = get_connection()
    cursor = conn.execute(
        """INSERT INTO incidents
           (raw_log, error_type, affected_system, severity,
            severity_confidence, report, processing_time)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (raw_log, error_type, affected_system, severity,
         severity_confidence, report, processing_time)
    )
    conn.commit()
    incident_id = cursor.lastrowid
    conn.close()
    return incident_id


def get_incidents():
    """Dashboard list — summary only, no raw_log or report."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT id, timestamp, error_type, affected_system,
                  severity, severity_confidence, processing_time
           FROM incidents ORDER BY id DESC"""
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_incident_by_id(incident_id):
    """Report page — full record including report markdown."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM incidents WHERE id = ?", (incident_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# Auto-initialize on import
init_db()