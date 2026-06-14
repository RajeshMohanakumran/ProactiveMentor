"""
MediPlan AI — FastAPI backend (multi-tenant).

Responsibilities:
  - REST API for Streamlit frontend (plan, profile, chat, progress)
  - APScheduler running in background — fires proactive agent at exact study
    times, for EVERY registered user independently
  - Dynamic schedule: reads each user's per-day schedule from DB every check
  - No hardcoded timings — everything driven by each user's saved schedule

Multi-tenancy: every endpoint takes a `user_id` query parameter. The frontend
generates a random user_id per browser session (stored in the URL via
?uid=...) so different visitors never see or overwrite each other's data.
"""
import sys, os, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")   # load GROQ_API_KEY etc.

from contextlib import asynccontextmanager
from datetime import datetime, date
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from shared.db import (
    init_db, get_profile, save_profile, update_schedule, get_all_user_ids,
    get_plan, get_stats, mark_task, add_message, get_messages,
    get_last_proactive, detect_phase, set_state, get_state,
)
from backend.agents.graph import run_planner, run_proactive, run_tutor, run_replan

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mediplan")


# ── Scheduler logic — runs for EVERY registered user ──────────────────────────

def check_and_fire_proactive():
    """
    Runs every minute via APScheduler.
    For each registered user, reads their dynamic schedule and fires the
    proactive agent at the exact minute their study window starts.
    """
    for user_id in get_all_user_ids():
        try:
            _check_user_proactive(user_id)
        except Exception as e:
            log.error(f"Scheduler error for user {user_id}: {e}")


def _check_user_proactive(user_id: str):
    profile = get_profile(user_id)
    if not profile:
        return

    now       = datetime.now()
    today_key = now.strftime("%a").lower()   # mon, tue, wed ...
    schedule  = profile.get("schedule", {})  # {mon: [{start:"18:00", end:"20:00"}], ...}
    today_slots = schedule.get(today_key, [])

    if not today_slots:
        # No slots configured for today — check for behind-schedule trigger
        _check_drift_trigger(user_id, profile)
        return

    for slot in today_slots:
        try:
            slot_start = datetime.strptime(slot["start"], "%H:%M").replace(
                year=now.year, month=now.month, day=now.day
            )
            # Fire if we're within 1.5 minutes of the slot start
            diff_mins = (now - slot_start).total_seconds() / 60
            if 0 <= diff_mins <= 1.5:
                # Avoid double-firing in the same slot
                last_fired_key = f"last_fired_{today_key}_{slot['start']}"
                last_fired_date = get_state(user_id, last_fired_key)
                if last_fired_date == date.today().isoformat():
                    continue

                log.info(f"Firing proactive agent for user {user_id}, slot {slot['start']}")
                msg = run_proactive(user_id, "study_time")
                if msg:
                    add_message(user_id, "assistant", msg, "tutor")
                    set_state(user_id, last_fired_key, date.today().isoformat())
                    log.info(f"Proactive message added for user {user_id}")
        except Exception as e:
            log.error(f"Scheduler error for user {user_id}, slot {slot}: {e}")


def _check_drift_trigger(user_id: str, profile: dict):
    """Secondary check — fire if student is significantly behind."""
    try:
        stats = get_stats(user_id)
        total = stats.get("total", 0)
        if total == 0:
            return
        done  = stats.get("done", 0)
        dr    = (datetime.strptime(profile["exam_date"], "%Y-%m-%d").date() - date.today()).days
        if dr <= 0:
            return
        total_days = max(dr + (total // 3), 1)
        expected   = total * (1 - dr / total_days)
        drift      = max(0, (expected - done) / max(expected, 1))
        if drift > 0.35:
            last = get_state(user_id, "last_drift_check")
            if last == date.today().isoformat():
                return
            log.info(f"Drift {drift:.2f} for user {user_id} — firing behind_schedule trigger")
            msg = run_proactive(user_id, "behind_schedule")
            if msg:
                add_message(user_id, "assistant", msg, "tutor")
                set_state(user_id, "last_drift_check", date.today().isoformat())
    except Exception as e:
        log.error(f"Drift check error for user {user_id}: {e}")


# Exam proximity trigger — daily, checked every morning
def check_exam_proximity():
    for user_id in get_all_user_ids():
        try:
            profile = get_profile(user_id)
            if not profile:
                continue
            dr = (datetime.strptime(profile["exam_date"], "%Y-%m-%d").date() - date.today()).days
            if dr in (30, 14, 7, 3, 1):
                last = get_state(user_id, f"exam_proximity_{dr}")
                if last == date.today().isoformat():
                    continue
                log.info(f"Exam proximity trigger for user {user_id}: {dr} days remaining")
                msg = run_proactive(user_id, "exam_near")
                if msg:
                    add_message(user_id, "assistant", msg, "tutor")
                    set_state(user_id, f"exam_proximity_{dr}", date.today().isoformat())
        except Exception as e:
            log.error(f"Exam proximity error for user {user_id}: {e}")


scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
scheduler.add_job(
    check_and_fire_proactive,
    trigger=IntervalTrigger(minutes=1),
    id="proactive_check",
    replace_existing=True,
)
scheduler.add_job(
    check_exam_proximity,
    trigger="cron",
    hour=7, minute=0,    # check every morning at 7 AM IST
    id="exam_proximity",
    replace_existing=True,
)


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler.start()
    log.info("MediPlan AI backend started — scheduler running (multi-tenant)")
    yield
    scheduler.shutdown()
    log.info("Scheduler stopped")


app = FastAPI(title="MediPlan AI", version="2.1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handler ──────────────────────────────────────────────────
# Guarantees every error reaches the frontend as readable JSON, even if it
# happens outside a route's own try/except.

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.error(f"‼ Unhandled error on {request.method} {request.url.path}:\n" + traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )


# ── Pydantic models ───────────────────────────────────────────────────────────

class ProfileIn(BaseModel):
    name:            str
    exam_name:       str
    exam_date:       str
    subjects:        list[str]
    weak_areas:      list[str] = []
    hours_per_day:   float = 4.0
    schedule:        dict  = {}    # {mon:[{start,end}], ...}
    telegram_chat_id: str | None = None


class ScheduleIn(BaseModel):
    schedule: dict    # {mon:[{start:"18:00",end:"20:00"}], ...}


class ChatIn(BaseModel):
    message: str


class TaskAction(BaseModel):
    task_id: int
    status:  str    # done / skipped


class ProactiveIn(BaseModel):
    trigger_type: str = "study_time"


# ── Routes ────────────────────────────────────────────────────────────────────
# Every route takes `user_id: str` as a required query parameter, e.g.
#   GET /profile?user_id=abc123
#   POST /chat?user_id=abc123   (body: {"message": "..."})

@app.get("/health")
def health():
    return {"status": "ok", "scheduler": scheduler.running}


# Profile
@app.post("/profile")
def create_profile(user_id: str, data: ProfileIn):
    save_profile(user_id, data.model_dump())
    return {"ok": True}


@app.get("/profile")
def read_profile(user_id: str):
    p = get_profile(user_id)
    if not p:
        raise HTTPException(404, "No profile found")
    return p


# Schedule (separate endpoint — user can update daily schedule without redoing full setup)
@app.put("/schedule")
def update_schedule_endpoint(user_id: str, data: ScheduleIn):
    update_schedule(user_id, data.schedule)
    return {"ok": True}


# Plan
@app.post("/plan/generate")
def generate_plan(user_id: str):
    profile = get_profile(user_id)
    if not profile:
        raise HTTPException(400, "No profile. Create profile first.")
    try:
        result = run_planner(profile)
    except Exception as e:
        log.error("plan/generate crashed:\n" + traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {e}")

    if result.get("error"):
        log.error(f"plan/generate agent error: {result['error']}")
        raise HTTPException(500, result["error"])
    return {"tasks": len(result.get("plan", [])), "phase": result.get("phase")}


@app.get("/plan")
def get_full_plan(user_id: str, date_str: str | None = None):
    return get_plan(user_id, date_str)


@app.post("/plan/replan")
def replan(user_id: str):
    result = run_replan(user_id)
    if result.get("error"):
        raise HTTPException(500, result["error"])
    return {"ok": True, "proactive_msg": result.get("proactive_msg", "")}


@app.post("/task")
def update_task(user_id: str, data: TaskAction):
    mark_task(user_id, data.task_id, data.status)
    return {"ok": True}


# Progress
@app.get("/progress")
def progress(user_id: str):
    profile = get_profile(user_id)
    stats   = get_stats(user_id)
    phase   = detect_phase(profile["exam_date"]) if profile else "sprint"
    dr      = 0
    if profile:
        try:
            dr = (datetime.strptime(profile["exam_date"], "%Y-%m-%d").date() - date.today()).days
        except Exception:
            pass
    return {**stats, "phase": phase, "days_remaining": dr}


# Chat
@app.post("/chat")
def chat(user_id: str, data: ChatIn):
    try:
        history  = get_messages(user_id, "tutor", limit=20)
        add_message(user_id, "user", data.message, "tutor")
        response = run_tutor(user_id, data.message, history)
        add_message(user_id, "assistant", response, "tutor")
        return {"response": response}
    except Exception as e:
        log.error("‼ /chat crashed:\n" + traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@app.get("/chat/history")
def chat_history(user_id: str, limit: int = 40):
    return get_messages(user_id, "tutor", limit)


# Proactive (manual trigger for testing / Streamlit fallback)
@app.post("/proactive/trigger")
def trigger_proactive(user_id: str, data: ProactiveIn):
    try:
        msg = run_proactive(user_id, data.trigger_type)
        if msg:
            add_message(user_id, "assistant", msg, "tutor")
        return {"message": msg}
    except Exception as e:
        log.error("‼ /proactive/trigger crashed:\n" + traceback.format_exc())
        raise HTTPException(500, f"{type(e).__name__}: {e}")


@app.get("/proactive/last")
def last_proactive(user_id: str):
    return get_last_proactive(user_id) or {}


# Scheduler status (for debugging)
@app.get("/scheduler/status")
def scheduler_status():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id":       job.id,
            "next_run": str(job.next_run_time),
        })
    return {
        "running": scheduler.running,
        "jobs": jobs,
        "registered_users": len(get_all_user_ids()),
    }
