"""
Run this once if you still get "database is locked" after replacing db.py.

Usage:
    python fix_db_lock.py

This stops any stuck WAL/journal state by reopening the DB and forcing
a checkpoint, and re-applies WAL mode cleanly.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "mediplan.db"

if not DB_PATH.exists():
    print(f"No DB found at {DB_PATH} — nothing to fix. It will be created fresh.")
else:
    print(f"Fixing {DB_PATH} ...")
    conn = sqlite3.connect(str(DB_PATH), timeout=60)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.commit()
        print("✅ WAL checkpoint complete. Database should be unlocked now.")
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nIf this still fails, stop ALL running processes "
              "(uvicorn + streamlit), then delete these files and restart:")
        print(f"  - {DB_PATH}")
        print(f"  - {DB_PATH}-wal")
        print(f"  - {DB_PATH}-shm")
    finally:
        conn.close()