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
    except requests.exceptions.ConnectionError:
        return {"_error": f"Cannot reach backend at {BACKEND_URL}. Is FastAPI running?"}
    except requests.exceptions.Timeout:
        return {"_error": "Backend timed out."}
    except Exception as e:
        return {"_error": str(e)}


def _post(path: str, data: dict = None):
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=data or {}, timeout=90)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"_error": f"Cannot reach backend at {BACKEND_URL}. Is FastAPI running?"}
    except requests.exceptions.Timeout:
        return {"_error": "Backend timed out — LLM call may be taking too long."}
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"_error": f"Backend error: {detail}"}
    except Exception as e:
        return {"_error": str(e)}


def _put(path: str, data: dict = None):
    try:
        r = requests.put(f"{BACKEND_URL}{path}", json=data or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"_error": f"Cannot reach backend at {BACKEND_URL}. Is FastAPI running?"}
    except Exception as e:
        return {"_error": str(e)}


# ── Public API ────────────────────────────────────────────────────────────────

def save_profile(profile: dict):
    return _post("/profile", profile)


def get_profile():
    result = _get("/profile")
    if result is None or "_error" in result:
        return None
    return result


def update_schedule(schedule: dict):
    return _put("/schedule", {"schedule": schedule})


def generate_plan():
    return _post("/plan/generate")


def get_plan(date_str: str = None):
    params = {"date_str": date_str} if date_str else {}
    result = _get("/plan", params)
    if result is None or (isinstance(result, dict) and "_error" in result):
        return []
    return result


def replan():
    return _post("/plan/replan")


def mark_task(task_id: int, status: str):
    return _post("/task", {"task_id": task_id, "status": status})


def get_progress():
    result = _get("/progress")
    if result is None or "_error" in result:
        return {}
    return result


def send_chat(message: str):
    """Returns (response_text, error_str_or_None)."""
    result = _post("/chat", {"message": message})
    if result is None:
        return "", "No response from backend."
    if "_error" in result:
        return "", result["_error"]
    return result.get("response", ""), None


def get_chat_history(limit: int = 40):
    """Returns (history_list, error_str_or_None)."""
    result = _get("/chat/history", {"limit": limit})
    if result is None:
        return [], "No response from backend."
    if isinstance(result, dict) and "_error" in result:
        return [], result["_error"]
    return result, None


def trigger_proactive(trigger_type: str = "study_time"):
    return _post("/proactive/trigger", {"trigger_type": trigger_type})


def get_last_proactive():
    result = _get("/proactive/last")
    if result is None or "_error" in result:
        return {}
    return result


def health_check() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False