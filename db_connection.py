"""
db_connection.py
Campus Equipment Management System - Oracle connectivity.

Install:
    python -m pip install oracledb

Set these Windows environment variables before running:
    set ORA_HOST=localhost
    set ORA_PORT=1521
    set ORA_SERVICE=XEPDB1
    set ORA_USER=YOUR_ORACLE_USERNAME
    set ORA_PASSWORD=YOUR_ORACLE_PASSWORD

For Oracle Database Free, use ORA_SERVICE=FREEPDB1 if that is the
service name shown by your installation.
"""

import os
from contextlib import contextmanager
import oracledb

DB_HOST = os.getenv("ORA_HOST", "localhost")
DB_PORT = int(os.getenv("ORA_PORT", "1521"))
DB_SERVICE = os.getenv("ORA_SERVICE", "XEPDB1")
DB_USER = os.getenv("ORA_USER", "CAMPUS_USER")
DB_PASSWORD = os.getenv("ORA_PASSWORD", "Campus123")

DB_DSN = f"{DB_HOST}:{DB_PORT}/{DB_SERVICE}"


def get_connection():
    """Create a new Oracle connection."""
    if not DB_USER or not DB_PASSWORD:
        raise RuntimeError(
            "Oracle credentials are not configured. Set ORA_USER and ORA_PASSWORD."
        )
    try:
        return oracledb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            dsn=DB_DSN
        )
    except oracledb.Error as exc:
        raise RuntimeError(
            f"Could not connect to Oracle at {DB_DSN} as {DB_USER}. "
            f"Check Oracle listener/service, username and password. "
            f"Original error: {exc}"
        ) from exc


@contextmanager
def get_cursor(commit=False):
    """
    Open connection/cursor, optionally commit, rollback on DB error,
    and always close both resources.
    """
    conn = get_connection()
    cur = conn.cursor()
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def test_connection():
    """Return connection information if Oracle is reachable."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT
                SYS_CONTEXT('USERENV', 'SESSION_USER'),
                SYS_CONTEXT('USERENV', 'SERVICE_NAME'),
                TO_CHAR(SYSDATE, 'YYYY-MM-DD HH24:MI:SS')
            FROM DUAL
        """)
        user, service, server_time = cur.fetchone()
        return {
            "user": user,
            "service": service,
            "server_time": server_time,
            "dsn": DB_DSN
        }


if __name__ == "__main__":
    try:
        print("Oracle connection successful:")
        print(test_connection())
    except Exception as exc:
        print(f"CONNECTION FAILED: {exc}")
