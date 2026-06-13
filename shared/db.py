"""
Shared database layer — used by both FastAPI backend and Streamlit frontend.

Design: ONE persistent SQLite connection for the whole process, guarded by a
single threading.Lock. All reads and writes go through this lock.

Why: this app has a single user, and concurrent access only comes from
(1) FastAPI request handlers and (2) the APScheduler background thread.
Per-call connections + WAL mode still hit "database is locked" on Windows
under this pattern (multiple short-lived connections from different threads).
A single connection + lock removes the race entirely — every DB op is
serialized, which is irrelevant for performance at this scale (single user,
SQLite ops take microseconds; only LLM calls are slow, and those don't hold
the lock).
"""
import sqlite3, json, threading
from pathlib import Path
from datetime import date, datetime

DB_PATH = Path(__file__).parent.parent / "mediplan.db"

_lock = threading.Lock()
_conn: sqlite3.Connection | None = None


def _get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=30)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=30000")
        _conn.execute("PRAGMA foreign_keys=ON")
    return _conn


def init_db():
    with _lock:
        conn = _get_conn()
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_profile (
            id            INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            exam_name     TEXT NOT NULL,
            exam_date     TEXT NOT NULL,
            subjects      TEXT NOT NULL,          -- JSON list
            weak_areas    TEXT DEFAULT '[]',      -- JSON list
            hours_per_day REAL DEFAULT 4.0,
            schedule      TEXT DEFAULT '{}',      -- JSON: {mon:[{start,end}], tue:[], ...}
            telegram_chat_id TEXT DEFAULT NULL,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS study_plan (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_date     TEXT NOT NULL,
            subject       TEXT NOT NULL,
            topic         TEXT NOT NULL,
            subtopics     TEXT DEFAULT '[]',      -- JSON list
            duration_mins INTEGER DEFAULT 60,
            priority      TEXT DEFAULT 'medium',  -- high / medium / low
            session_type  TEXT DEFAULT 'learn',   -- learn / revise / practice
            status        TEXT DEFAULT 'pending', -- pending / done / skipped
            phase         TEXT DEFAULT 'sprint',  -- marathon/sprint/crunch/emergency
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            role          TEXT NOT NULL,          -- user / assistant
            content       TEXT NOT NULL,
            agent_type    TEXT DEFAULT 'tutor',
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS proactive_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_type  TEXT NOT NULL,
            phase         TEXT,
            message       TEXT NOT NULL,
            delivered     INTEGER DEFAULT 0,
            created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scheduler_state (
            key           TEXT PRIMARY KEY,
            value         TEXT,
            updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        conn.commit()


# ── Profile ───────────────────────────────────────────────────────────────────

def save_profile(p: dict):
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM user_profile")
        conn.execute("""
            INSERT INTO user_profile
                (name, exam_name, exam_date, subjects, weak_areas,
                 hours_per_day, schedule, telegram_chat_id)
            VALUES (?,?,?,?,?,?,?,?)
        """, (
            p["name"], p["exam_name"], p["exam_date"],
            json.dumps(p.get("subjects", [])),
            json.dumps(p.get("weak_areas", [])),
            p.get("hours_per_day", 4.0),
            json.dumps(p.get("schedule", {})),
            p.get("telegram_chat_id"),
        ))
        conn.commit()


def get_profile() -> dict | None:
    with _lock:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM user_profile LIMIT 1").fetchone()
    if not row:
        return None
    p = dict(row)
    for k in ("subjects", "weak_areas", "schedule"):
        try:
            p[k] = json.loads(p[k] or "[]")
        except Exception:
            p[k] = []
    return p


def update_schedule(schedule: dict):
    with _lock:
        conn = _get_conn()
        conn.execute(
            "UPDATE user_profile SET schedule=?, updated_at=CURRENT_TIMESTAMP",
            (json.dumps(schedule),)
        )
        conn.commit()


# ── Study plan ────────────────────────────────────────────────────────────────

def save_plan(tasks: list):
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM study_plan")
        conn.executemany("""
            INSERT INTO study_plan
                (plan_date, subject, topic, subtopics,
                 duration_mins, priority, session_type, phase)
            VALUES (?,?,?,?,?,?,?,?)
        """, [(
            t["date"], t["subject"], t["topic"],
            json.dumps(t.get("subtopics", [])),
            t.get("duration_mins", 60),
            t.get("priority", "medium"),
            t.get("session_type", "learn"),
            t.get("phase", "sprint"),
        ) for t in tasks])
        conn.commit()


def get_plan(date_str: str | None = None) -> list:
    with _lock:
        conn = _get_conn()
        if date_str:
            rows = conn.execute(
                "SELECT * FROM study_plan WHERE plan_date=? ORDER BY id",
                (date_str,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM study_plan ORDER BY plan_date, id"
            ).fetchall()
    result = []
    for r in rows:
        t = dict(r)
        try:
            t["subtopics"] = json.loads(t["subtopics"])
        except Exception:
            t["subtopics"] = []
        result.append(t)
    return result


def mark_task(task_id: int, status: str):
    with _lock:
        conn = _get_conn()
        conn.execute("UPDATE study_plan SET status=? WHERE id=?", (status, task_id))
        conn.commit()


def get_stats() -> dict:
    with _lock:
        conn = _get_conn()
        total = conn.execute("SELECT COUNT(*) FROM study_plan").fetchone()[0]
        done  = conn.execute("SELECT COUNT(*) FROM study_plan WHERE status='done'").fetchone()[0]
        today = date.today().isoformat()
        today_done = conn.execute(
            "SELECT COUNT(*) FROM study_plan WHERE plan_date=? AND status='done'", (today,)
        ).fetchone()[0]
        today_total = conn.execute(
            "SELECT COUNT(*) FROM study_plan WHERE plan_date=?", (today,)
        ).fetchone()[0]
        by_subj = conn.execute("""
            SELECT subject,
                   COUNT(*) as total,
                   SUM(CASE WHEN status='done' THEN 1 ELSE 0 END) as done
            FROM study_plan GROUP BY subject
        """).fetchall()
    return {
        "total": total, "done": done,
        "today_done": today_done, "today_total": today_total,
        "by_subject": [dict(r) for r in by_subj],
    }


# ── Conversations ─────────────────────────────────────────────────────────────

def add_message(role: str, content: str, agent_type: str = "tutor"):
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO conversations (role,content,agent_type) VALUES (?,?,?)",
            (role, content, agent_type)
        )
        conn.commit()


def get_messages(agent_type: str = "tutor", limit: int = 40) -> list:
    with _lock:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT * FROM conversations WHERE agent_type=? ORDER BY created_at DESC LIMIT ?",
            (agent_type, limit)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


# ── Proactive log ─────────────────────────────────────────────────────────────

def log_proactive(trigger: str, phase: str, message: str):
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO proactive_log (trigger_type,phase,message) VALUES (?,?,?)",
            (trigger, phase, message)
        )
        conn.commit()


def get_last_proactive() -> dict | None:
    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT * FROM proactive_log ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    return dict(row) if row else None


def mark_proactive_delivered(pid: int):
    with _lock:
        conn = _get_conn()
        conn.execute("UPDATE proactive_log SET delivered=1 WHERE id=?", (pid,))
        conn.commit()


# ── Scheduler state ───────────────────────────────────────────────────────────

def set_state(key: str, value: str):
    with _lock:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO scheduler_state (key,value,updated_at) VALUES (?,?,CURRENT_TIMESTAMP)",
            (key, value)
        )
        conn.commit()


def get_state(key: str) -> str | None:
    with _lock:
        conn = _get_conn()
        row = conn.execute(
            "SELECT value FROM scheduler_state WHERE key=?", (key,)
        ).fetchone()
    return row["value"] if row else None


# ── Phase detection — the key logic ──────────────────────────────────────────

def detect_phase(exam_date_str: str) -> str:
    """
    Dynamically detect study phase based on days remaining.
    No hardcoded user-facing modes — this happens silently in the background.
    """
    try:
        ed = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
        dr = (ed - date.today()).days
    except Exception:
        return "sprint"

    if dr > 60:   return "marathon"
    if dr > 14:   return "sprint"
    if dr > 3:    return "crunch"
    return "emergency"


PHASE_RULES = {
    "marathon": (
        "Spread topics evenly with spaced repetition every 7 days. "
        "Include 1 rest day per week. Deep coverage of all topics."
    ),
    "sprint": (
        "Prioritise high-yield topics first. Include daily practice questions. "
        "Compact but thorough schedule."
    ),
    "crunch": (
        "High-yield topics ONLY. 30–45 min focused sessions. "
        "Revision every 2 days. No new topics after day 3 of this phase."
    ),
    "emergency": (
        "Top 3 high-yield topics per subject ONLY — topics the student has already studied. "
        "20-minute rapid reviews. Key mnemonics only. Prioritise what's already in memory."
    ),
}