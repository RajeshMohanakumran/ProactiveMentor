"""
Clears old chat messages so you can test with fresh data.
Run this from the project root: python clear_chat.py
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "mediplan.db"

if not DB_PATH.exists():
    print("No database found — nothing to clear.")
else:
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.execute("DELETE FROM conversations")
    cur2 = conn.execute("DELETE FROM proactive_log")
    conn.commit()
    print(f"Cleared {cur.rowcount} chat messages and {cur2.rowcount} proactive logs.")
    conn.close()
