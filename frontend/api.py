"""
HTTP client used by all Streamlit pages to talk to the FastAPI backend.
Falls back to direct DB/agent calls if backend is not running (dev mode).
"""
import os
import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _get(path: str, params: dict = None):
    try:
        r = requests.get(f"{BACKEND_URL}{path}", params=params, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Backend error: {e}")
        return None


def _post(path: str, data: dict = None):
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=data or {}, timeout=60)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Backend error: {e}")
        return None


def _put(path: str, data: dict = None):
    try:
        r = requests.put(f"{BACKEND_URL}{path}", json=data or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Backend error: {e}")
        return None


# ── Public API ────────────────────────────────────────────────────────────────

def save_profile(profile: dict):
    return _post("/profile", profile)


def get_profile():
    return _get("/profile")


def update_schedule(schedule: dict):
    return _put("/schedule", {"schedule": schedule})


def generate_plan():
    return _post("/plan/generate")


def get_plan(date_str: str = None):
    params = {"date_str": date_str} if date_str else {}
    return _get("/plan", params) or []


def replan():
    return _post("/plan/replan")


def mark_task(task_id: int, status: str):
    return _post("/task", {"task_id": task_id, "status": status})


def get_progress():
    return _get("/progress") or {}


def send_chat(message: str):
    result = _post("/chat", {"message": message})
    return result.get("response", "") if result else ""


def get_chat_history(limit: int = 40):
    return _get("/chat/history", {"limit": limit}) or []


def trigger_proactive(trigger_type: str = "study_time"):
    return _post("/proactive/trigger", {"trigger_type": trigger_type})


def get_last_proactive():
    return _get("/proactive/last") or {}


def health_check() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
