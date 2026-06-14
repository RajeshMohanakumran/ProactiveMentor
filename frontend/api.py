"""
HTTP client used by all Streamlit pages to talk to the FastAPI backend.

Every function takes `user_id` as its first argument and passes it as a
query parameter to the backend — this is what makes the deployed app
multi-tenant: each browser session's user_id (from frontend/session.py)
scopes all reads/writes to that user's own data only.
"""
import os
import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


def _get(path: str, user_id: str, params: dict = None):
    p = {"user_id": user_id, **(params or {})}
    try:
        r = requests.get(f"{BACKEND_URL}{path}", params=p, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"_error": f"Cannot reach backend at {BACKEND_URL}. Is FastAPI running?"}
    except requests.exceptions.Timeout:
        return {"_error": "Backend timed out."}
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"_error": f"Backend error: {detail}"}
    except Exception as e:
        return {"_error": str(e)}


def _post(path: str, user_id: str, data: dict = None, params: dict = None):
    p = {"user_id": user_id, **(params or {})}
    try:
        r = requests.post(f"{BACKEND_URL}{path}", params=p, json=data or {}, timeout=90)
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


def _put(path: str, user_id: str, data: dict = None):
    p = {"user_id": user_id}
    try:
        r = requests.put(f"{BACKEND_URL}{path}", params=p, json=data or {}, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"_error": f"Cannot reach backend at {BACKEND_URL}. Is FastAPI running?"}
    except requests.exceptions.HTTPError as e:
        try:
            detail = e.response.json().get("detail", str(e))
        except Exception:
            detail = str(e)
        return {"_error": f"Backend error: {detail}"}
    except Exception as e:
        return {"_error": str(e)}


# ── Public API — every function scoped by user_id ──────────────────────────────

def get_profile(user_id: str):
    result = _get("/profile", user_id)
    if result is None or "_error" in result:
        return None
    return result


def save_profile(user_id: str, profile: dict):
    return _post("/profile", user_id, profile)


def update_schedule(user_id: str, schedule: dict):
    return _put("/schedule", user_id, {"schedule": schedule})


def generate_plan(user_id: str):
    return _post("/plan/generate", user_id)


def get_plan(user_id: str, date_str: str = None):
    params = {"date_str": date_str} if date_str else {}
    result = _get("/plan", user_id, params)
    if result is None or (isinstance(result, dict) and "_error" in result):
        return []
    return result


def replan(user_id: str):
    return _post("/plan/replan", user_id)


def mark_task(user_id: str, task_id: int, status: str):
    return _post("/task", user_id, {"task_id": task_id, "status": status})


def get_progress(user_id: str):
    result = _get("/progress", user_id)
    if result is None or "_error" in result:
        return {}
    return result


def send_chat(user_id: str, message: str):
    """Returns (response_text, error_str_or_None)."""
    result = _post("/chat", user_id, {"message": message})
    if result is None:
        return "", "No response from backend."
    if "_error" in result:
        return "", result["_error"]
    return result.get("response", ""), None


def get_chat_history(user_id: str, limit: int = 40):
    """Returns (history_list, error_str_or_None)."""
    result = _get("/chat/history", user_id, {"limit": limit})
    if result is None:
        return [], "No response from backend."
    if isinstance(result, dict) and "_error" in result:
        return [], result["_error"]
    return result, None


def trigger_proactive(user_id: str, trigger_type: str = "study_time"):
    return _post("/proactive/trigger", user_id, {"trigger_type": trigger_type})


def get_last_proactive(user_id: str):
    result = _get("/proactive/last", user_id)
    if result is None or "_error" in result:
        return {}
    return result


def health_check() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=3)
        return r.status_code == 200
    except Exception:
        return False
