"""
MediPlan AI — Proper LangGraph graph.

Three separate flows, each a real StateGraph:
  1. PlannerGraph   — initial plan generation (Setup → RAG → Planner → Save)
  2. ProactiveGraph — proactive message generation (Progress → PhaseCheck → Proactive)
  3. TutorGraph     — chat response with context routing

Conditional edges determine which path is taken at runtime.
"""
import json, re, sys
from datetime import date, datetime
from pathlib import Path
from typing import TypedDict, Annotated, Literal

sys.path.insert(0, str(Path(__file__).parent.parent))

from langgraph.graph import StateGraph, END
from shared.db import (
    get_profile, get_plan, get_stats, save_plan,
    log_proactive, detect_phase, PHASE_RULES,
)
from shared.llm import llm_call
from shared.syllabus import get_syllabus_context
from shared.prompts import (
    PLANNER_SYSTEM, PLANNER_USER,
    PROACTIVE_SYSTEM, PROACTIVE_USER,
    TUTOR_SYSTEM, REPLAN_SYSTEM, REPLAN_USER,
)


# ── Shared helpers ────────────────────────────────────────────────────────────

def days_left(exam_date_str: str) -> int:
    try:
        ed = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
        return max((ed - date.today()).days, 0)
    except Exception:
        return 30


def robust_parse_json(text: str) -> list:
    """Parse JSON array — recovers from truncation and markdown fences."""
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("`").strip()
    start = text.find("[")
    if start == -1:
        raise ValueError("No JSON array in response")
    text = text[start:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Truncation recovery
    for end in range(len(text), 0, -1):
        for suffix in ("", "]", "}]"):
            try:
                result = json.loads(text[:end] + suffix)
                if isinstance(result, list) and result:
                    return result
            except json.JSONDecodeError:
                continue
    raise ValueError("Could not recover JSON from LLM response")


# ════════════════════════════════════════════════════════════════════════════
# 1.  PLANNER GRAPH
#     START → rag_node → phase_node → planner_node → END
#     Conditional: if emergency phase → emergency_planner_node (revision only)
# ════════════════════════════════════════════════════════════════════════════

class PlannerState(TypedDict):
    profile:          dict
    syllabus_context: str
    phase:            str
    plan_days:        int
    plan:             list
    error:            str


def rag_node(state: PlannerState) -> PlannerState:
    ctx = get_syllabus_context(state["profile"].get("subjects", []))
    return {**state, "syllabus_context": ctx}


def phase_node(state: PlannerState) -> PlannerState:
    phase     = detect_phase(state["profile"]["exam_date"])
    dr        = days_left(state["profile"]["exam_date"])
    plan_days = min(dr, 21) if dr > 1 else 1
    return {**state, "phase": phase, "plan_days": plan_days}


def _build_plan_prompt(state: PlannerState) -> tuple[str, str]:
    p  = state["profile"]
    dr = days_left(p["exam_date"])
    user = PLANNER_USER.format(
        name=p["name"], exam_name=p["exam_name"], exam_date=p["exam_date"],
        days_remaining=dr, phase=state["phase"],
        subjects=", ".join(p.get("subjects", [])),
        weak_areas=", ".join(p.get("weak_areas", [])),
        hours_per_day=p.get("hours_per_day", 4),
        plan_days=state["plan_days"],
        start_date=date.today().isoformat(),
        phase_rule=PHASE_RULES[state["phase"]],
        syllabus_context=state["syllabus_context"],
    )
    return PLANNER_SYSTEM, user


def planner_node(state: PlannerState) -> PlannerState:
    system, user = _build_plan_prompt(state)
    try:
        raw  = llm_call(system, user, temperature=0.2, max_tokens=8192)
        plan = robust_parse_json(raw)
        save_plan(state["profile"]["user_id"], plan)
        return {**state, "plan": plan}
    except Exception as e:
        return {**state, "error": str(e)}


def emergency_planner_node(state: PlannerState) -> PlannerState:
    """
    Emergency phase — only plan revision of topics already in the database.
    Does NOT call LLM for new topics; generates a lightweight revision plan.
    """
    existing = [t for t in get_plan(state["profile"]["user_id"]) if t["status"] in ("done", "pending")]
    # Pick top high-priority topics the student has already seen
    high     = [t for t in existing if t.get("priority") == "high"][:6]
    medium   = [t for t in existing if t.get("priority") == "medium"][:4]
    revision_pool = high + medium

    today_str = date.today().isoformat()
    plan = [{
        "date":         today_str,
        "subject":      t["subject"],
        "topic":        t["topic"],
        "subtopics":    t.get("subtopics", []),
        "duration_mins": 20,
        "priority":     t.get("priority", "high"),
        "session_type": "revise",
        "phase":        "emergency",
    } for t in revision_pool]

    # If somehow empty, fall back to normal planner
    if not plan:
        return planner_node(state)

    save_plan(state["profile"]["user_id"], plan)
    return {**state, "plan": plan}


def route_by_phase(state: PlannerState) -> Literal["planner_node", "emergency_planner_node"]:
    """Conditional edge — emergency phase gets special revision-only planner."""
    return "emergency_planner_node" if state["phase"] == "emergency" else "planner_node"


def build_planner_graph() -> StateGraph:
    g = StateGraph(PlannerState)
    g.add_node("rag_node",            rag_node)
    g.add_node("phase_node",          phase_node)
    g.add_node("planner_node",        planner_node)
    g.add_node("emergency_planner_node", emergency_planner_node)

    g.set_entry_point("rag_node")
    g.add_edge("rag_node",   "phase_node")
    g.add_conditional_edges(
        "phase_node",
        route_by_phase,
        {
            "planner_node":           "planner_node",
            "emergency_planner_node": "emergency_planner_node",
        }
    )
    g.add_edge("planner_node",           END)
    g.add_edge("emergency_planner_node", END)
    return g.compile()


# ════════════════════════════════════════════════════════════════════════════
# 2.  PROACTIVE GRAPH
#     START → progress_node → drift_check_node → [nudge | skip | replan]
# ════════════════════════════════════════════════════════════════════════════

class ProactiveState(TypedDict):
    profile:         dict
    trigger_type:    str
    stats:           dict
    phase:           str
    drift:           float    # 0–1, how far behind
    proactive_msg:   str
    should_replan:   bool
    new_plan:        list
    error:           str


def progress_node(state: ProactiveState) -> ProactiveState:
    try:
        stats = get_stats(state["profile"]["user_id"])
        phase = detect_phase(state["profile"]["exam_date"])
        total = stats.get("total", 1)
        done  = stats.get("done", 0)
        # Drift = proportion of expected completions that are missing
        dr        = days_left(state["profile"]["exam_date"])
        total_days_originally = max(dr + (total // 3), 1)  # rough estimate
        expected_done = total * (1 - dr / total_days_originally) if total_days_originally > dr else total
        drift = max(0.0, min(1.0, (expected_done - done) / max(expected_done, 1)))
        return {**state, "stats": stats, "phase": phase, "drift": round(drift, 2)}
    except Exception as e:
        return {**state, "stats": {}, "phase": "sprint", "drift": 0.0, "error": str(e)}


def drift_router(state: ProactiveState) -> Literal["proactive_node", "replan_node", "skip_node"]:
    """
    Conditional edge — decides what to do based on drift and trigger type.
    drift > 0.4 and explicit trigger → replan
    any study_time trigger → proactive message
    drift very low and no trigger urgency → skip (do nothing)
    """
    trigger = state["trigger_type"]
    drift   = state["drift"]
    phase   = state["phase"]

    if trigger == "replan_requested":
        return "replan_node"
    if drift > 0.4 and trigger in ("behind_schedule", "scheduled_check"):
        return "replan_node"
    if trigger in ("study_time", "exam_near", "streak_break", "behind_schedule", "scheduled_check"):
        return "proactive_node"
    return "skip_node"


def proactive_node(state: ProactiveState) -> ProactiveState:
    profile  = state["profile"]
    today    = date.today().isoformat()
    today_tasks = get_plan(profile["user_id"], today)
    pending  = [t for t in today_tasks if t["status"] == "pending"]
    done_t   = [t for t in today_tasks if t["status"] == "done"]

    pending_str  = ", ".join(f"{t['subject']}: {t['topic']}" for t in pending[:4]) or "all done!"
    done_str     = ", ".join(t["topic"] for t in done_t[:3]) or "nothing yet"

    user = PROACTIVE_USER.format(
        name=profile["name"],
        phase=state["phase"],
        days_remaining=days_left(profile["exam_date"]),
        exam_name=profile["exam_name"],
        pending_topics=pending_str,
        completed_today=done_str,
        current_time=datetime.now().strftime("%I:%M %p"),
        weak_areas=", ".join(profile.get("weak_areas", [])),
        trigger_type=state["trigger_type"],
    )
    try:
        msg = llm_call(PROACTIVE_SYSTEM, user, temperature=0.8, fast=True, max_tokens=300)
        log_proactive(profile["user_id"], state["trigger_type"], state["phase"], msg)
        return {**state, "proactive_msg": msg}
    except Exception as e:
        err = str(e)
        log_proactive(profile["user_id"], state["trigger_type"], state["phase"], f"[error: {err}]")
        return {**state, "proactive_msg": "", "error": err}


def replan_node(state: ProactiveState) -> ProactiveState:
    """Triggered when drift is high — generates a new compressed plan."""
    profile  = state["profile"]
    stats    = state["stats"]
    total    = stats.get("total", 1)
    done     = stats.get("done", 0)
    pct      = round(done / total * 100, 1) if total else 0
    dr       = days_left(profile["exam_date"])
    phase    = state["phase"]

    pending  = [t for t in get_plan(profile["user_id"]) if t["status"] == "pending"][:20]
    pending_str = "\n".join(f"- {t['subject']}: {t['topic']}" for t in pending)

    user = REPLAN_USER.format(
        completion_pct=pct,
        days_remaining=dr,
        pending_count=len(pending),
        pending_topics=pending_str,
        hours_per_day=profile.get("hours_per_day", 4),
        phase=phase,
        phase_rule=PHASE_RULES[phase],
        start_date=date.today().isoformat(),
    )
    try:
        raw  = llm_call(REPLAN_SYSTEM, user, temperature=0.2, max_tokens=8192)
        plan = robust_parse_json(raw)
        save_plan(profile["user_id"], plan)
        # Also send a proactive message about the replan
        updated_state = {**state, "new_plan": plan, "should_replan": True}
        return proactive_node(updated_state)
    except Exception as e:
        return {**state, "error": str(e)}


def skip_node(state: ProactiveState) -> ProactiveState:
    """Nothing to do — student is on track and not in a study window."""
    return {**state, "proactive_msg": ""}


def build_proactive_graph() -> StateGraph:
    g = StateGraph(ProactiveState)
    g.add_node("progress_node",  progress_node)
    g.add_node("proactive_node", proactive_node)
    g.add_node("replan_node",    replan_node)
    g.add_node("skip_node",      skip_node)

    g.set_entry_point("progress_node")
    g.add_conditional_edges(
        "progress_node",
        drift_router,
        {
            "proactive_node": "proactive_node",
            "replan_node":    "replan_node",
            "skip_node":      "skip_node",
        }
    )
    g.add_edge("proactive_node", END)
    g.add_edge("replan_node",    END)
    g.add_edge("skip_node",      END)
    return g.compile()


# ════════════════════════════════════════════════════════════════════════════
# 3.  TUTOR GRAPH
#     START → context_node → [topic_in_plan | off_topic] → tutor_node → END
# ════════════════════════════════════════════════════════════════════════════

class TutorState(TypedDict):
    profile:      dict
    user_message: str
    history:      list
    context:      str
    is_on_plan:   bool
    response:     str
    error:        str


def context_node(state: TutorState) -> TutorState:
    try:
        subjects = state["profile"].get("subjects", [])
        ctx      = get_syllabus_context(subjects)[:3000]
        today_tasks = get_plan(state["profile"]["user_id"], date.today().isoformat())
        plan_topics  = " ".join(t["topic"].lower() for t in today_tasks)
        msg_lower    = state["user_message"].lower()
        is_on_plan   = any(
            word in plan_topics
            for word in msg_lower.split()
            if len(word) > 4
        )
        return {**state, "context": ctx, "is_on_plan": is_on_plan}
    except Exception as e:
        # Don't let context-building crash the whole chat — degrade gracefully
        return {**state, "context": "", "is_on_plan": False, "error": f"context_node: {e}"}


def tutor_node(state: TutorState) -> TutorState:
    profile = state["profile"]
    dr      = days_left(profile["exam_date"])
    phase   = detect_phase(profile["exam_date"])

    today_tasks   = get_plan(profile["user_id"], date.today().isoformat())
    todays_topics = ", ".join(
        f"{t['subject']}: {t['topic']}" for t in today_tasks[:5]
    ) or "open revision"

    system = TUTOR_SYSTEM.format(
        name=profile["name"],
        exam_name=profile["exam_name"],
        phase=phase,
        days_remaining=dr,
        todays_topics=todays_topics,
        context=state["context"],
    )

    # Build history context (last 6 messages)
    hist = ""
    for m in state["history"][-6:]:
        role = "Student" if m["role"] == "user" else "MediPlan"
        hist += f"{role}: {m['content']}\n"

    full_user = f"Conversation so far:\n{hist}\nStudent: {state['user_message']}"
    try:
        response = llm_call(system, full_user, temperature=0.7, fast=True, max_tokens=1024)
        return {**state, "response": response}
    except Exception as e:
        err = str(e)
        return {
            **state,
            "error": err,
            "response": f"Sorry, something went wrong talking to the AI: {err}"
        }


def build_tutor_graph() -> StateGraph:
    g = StateGraph(TutorState)
    g.add_node("context_node", context_node)
    g.add_node("tutor_node",   tutor_node)
    g.set_entry_point("context_node")
    g.add_edge("context_node", "tutor_node")
    g.add_edge("tutor_node",   END)
    return g.compile()


# ── Public runner functions ───────────────────────────────────────────────────

_planner_app   = None
_proactive_app = None
_tutor_app     = None


def get_planner():
    global _planner_app
    if _planner_app is None:
        _planner_app = build_planner_graph()
    return _planner_app


def get_proactive():
    global _proactive_app
    if _proactive_app is None:
        _proactive_app = build_proactive_graph()
    return _proactive_app


def get_tutor():
    global _tutor_app
    if _tutor_app is None:
        _tutor_app = build_tutor_graph()
    return _tutor_app


def run_planner(profile: dict) -> dict:
    state: PlannerState = {
        "profile": profile, "syllabus_context": "",
        "phase": "", "plan_days": 21, "plan": [], "error": "",
    }
    return get_planner().invoke(state)


def run_proactive(user_id: str, trigger_type: str) -> str:
    profile = get_profile(user_id)
    if not profile:
        return ""
    state: ProactiveState = {
        "profile": profile, "trigger_type": trigger_type,
        "stats": {}, "phase": "", "drift": 0.0,
        "proactive_msg": "", "should_replan": False,
        "new_plan": [], "error": "",
    }
    result = get_proactive().invoke(state)
    return result.get("proactive_msg", "")


def run_replan(user_id: str) -> dict:
    profile = get_profile(user_id)
    if not profile:
        return {"error": "No profile"}
    state: ProactiveState = {
        "profile": profile, "trigger_type": "replan_requested",
        "stats": {}, "phase": "", "drift": 0.5,
        "proactive_msg": "", "should_replan": False,
        "new_plan": [], "error": "",
    }
    return get_proactive().invoke(state)


def run_tutor(user_id: str, user_message: str, history: list) -> str:
    profile = get_profile(user_id)
    if not profile:
        return "Please complete your profile setup first!"
    state: TutorState = {
        "profile": profile, "user_message": user_message,
        "history": history, "context": "",
        "is_on_plan": False, "response": "", "error": "",
    }
    result = get_tutor().invoke(state)
    return result.get("response", "Sorry, something went wrong.")
