import streamlit as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api import (get_profile, get_plan, get_chat_history,
                           send_chat, trigger_proactive, get_last_proactive,
                           health_check, BACKEND_URL)
from frontend.session import get_user_id
from shared.db import init_db
from datetime import date, datetime

init_db()
user_id = get_user_id()
profile = get_profile(user_id)
if not profile:
    st.warning("Set up your profile first.")
    if st.button("Setup →"): st.switch_page("pages/1_Setup.py")
    st.stop()

st.markdown("## 💬 Study Chat")
st.caption("The AI initiates at your scheduled study times — messages appear here automatically.")

# ── Auto-refresh every 30s so proactive messages appear without manual reload ──
# Pauses while the chat input is focused so it doesn't interrupt typing.
st.components.v1.html("""
<script>
(function() {
    let paused = false;
    const doc = window.parent.document;

    doc.addEventListener('focusin', (e) => {
        if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') paused = true;
    });
    doc.addEventListener('focusout', (e) => {
        if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') paused = false;
    });

    setInterval(() => {
        if (!paused) window.parent.location.reload();
    }, 30000);
})();
</script>
""", height=0)

# ── Backend status ────────────────────────────────────────────────────────────
backend_ok = health_check()
if not backend_ok:
    st.error(
        f"🔴 Cannot reach the FastAPI backend at `{BACKEND_URL}`.\n\n"
        "Chat won't work until it's running. Start it with:\n\n"
        "`uvicorn backend.main:app --reload --port 8000`"
    )

# ── Persistent error banner (survives reruns) ──────────────────────────────────
if st.session_state.get("chat_error"):
    st.error(f"⚠ {st.session_state['chat_error']}")
    if st.button("Dismiss"):
        st.session_state["chat_error"] = None
        st.rerun()

# ── Manual trigger controls ────────────────────────────────────────────────────
with st.expander("🔧 Test proactive triggers", expanded=False):
    st.caption("Normally fires automatically at your scheduled times. Use these to test.")
    c1,c2,c3 = st.columns(3)
    with c1:
        if st.button("▶ Study time", use_container_width=True, disabled=not backend_ok):
            with st.spinner("Generating..."):
                res = trigger_proactive(user_id, "study_time")
            if res and "_error" in res:
                st.session_state["chat_error"] = res["_error"]
            st.rerun()
    with c2:
        if st.button("⚠ Behind schedule", use_container_width=True, disabled=not backend_ok):
            with st.spinner("Generating..."):
                res = trigger_proactive(user_id, "behind_schedule")
            if res and "_error" in res:
                st.session_state["chat_error"] = res["_error"]
            st.rerun()
    with c3:
        if st.button("📅 Exam near", use_container_width=True, disabled=not backend_ok):
            with st.spinner("Generating..."):
                res = trigger_proactive(user_id, "exam_near")
            if res and "_error" in res:
                st.session_state["chat_error"] = res["_error"]
            st.rerun()

# ── Today's context ────────────────────────────────────────────────────────────
today_tasks = get_plan(user_id, date.today().isoformat())
pending = [t for t in today_tasks if t["status"]=="pending"]
if pending:
    topics_str = " · ".join(f"{t['subject']}: {t['topic']}" for t in pending[:4])
    st.markdown(f"""<div style='background:#0F1117;border:1px solid #1E2535;border-radius:8px;
    padding:8px 14px;margin-bottom:1rem;font-size:12px;color:#4A5568'>
    📋 Pending today: <span style='color:#CBD5E1'>{topics_str}</span></div>""",
    unsafe_allow_html=True)

# ── Last proactive ─────────────────────────────────────────────────────────────
last = get_last_proactive(user_id)
if last and last.get("created_at"):
    try:
        mins = int((datetime.now() - datetime.fromisoformat(last["created_at"])).total_seconds()//60)
        if mins < 180:
            st.markdown(f"""<div style='background:linear-gradient(135deg,#1a3a5c,#0d2137);
            border:1px solid #2563EB44;border-radius:14px;padding:1rem 1.25rem;margin-bottom:1rem'>
            <div style='font-size:10px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;
            color:#3B82F6;margin-bottom:6px'>🤖 MediPlan AI initiated {mins} mins ago · {last.get("trigger_type","")}</div>
            <div style='font-size:14px;color:#CBD5E1;line-height:1.65'>{last.get("message","")}</div>
            </div>""", unsafe_allow_html=True)
    except Exception:
        pass

# ── Chat history ───────────────────────────────────────────────────────────────
history, hist_error = get_chat_history(user_id, 40)
if hist_error and backend_ok:
    st.warning(f"Couldn't load chat history: {hist_error}")

if not history:
    st.markdown("""<div style='text-align:center;padding:3rem 1rem;color:#4A5568'>
    <div style='font-size:40px;margin-bottom:10px'>🩺</div>
    <div style='font-size:15px;color:#718096'>MediPlan AI will reach out at your study time</div>
    <div style='font-size:12px;margin-top:6px'>Or ask anything below</div>
    </div>""", unsafe_allow_html=True)
else:
    for msg in history:
        if msg["role"] == "user":
            st.markdown(f"""<div style='display:flex;justify-content:flex-end;margin:5px 0'>
            <div style='background:#1E3A5F;border-radius:12px 12px 2px 12px;padding:9px 13px;
            max-width:75%;font-size:13px;color:#E2E8F0;line-height:1.55'>{msg["content"]}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style='display:flex;margin:5px 0;gap:7px'>
            <div style='width:26px;height:26px;background:#1E2535;border-radius:50%;
            display:flex;align-items:center;justify-content:center;font-size:13px;
            flex-shrink:0;margin-top:2px'>🩺</div>
            <div style='background:#161B27;border:1px solid #1E2535;border-radius:12px 12px 12px 2px;
            padding:9px 13px;max-width:75%;font-size:13px;color:#CBD5E1;line-height:1.65'>
            {msg["content"]}</div></div>""", unsafe_allow_html=True)

# Optimistic "sending..." UI while waiting for backend
if st.session_state.get("chat_pending_msg"):
    pending_msg = st.session_state["chat_pending_msg"]
    st.markdown(f"""<div style='display:flex;justify-content:flex-end;margin:5px 0'>
    <div style='background:#1E3A5F;border-radius:12px 12px 2px 12px;padding:9px 13px;
    max-width:75%;font-size:13px;color:#E2E8F0;line-height:1.55;opacity:0.6'>{pending_msg}</div>
    </div>""", unsafe_allow_html=True)
    st.markdown("""<div style='display:flex;margin:5px 0;gap:7px'>
    <div style='width:26px;height:26px;background:#1E2535;border-radius:50%;
    display:flex;align-items:center;justify-content:center;font-size:13px;
    flex-shrink:0;margin-top:2px'>🩺</div>
    <div style='font-size:12px;color:#4A5568;padding-top:6px'>MediPlan AI is thinking...</div>
    </div>""", unsafe_allow_html=True)

# ── Input ──────────────────────────────────────────────────────────────────────
user_input = st.chat_input(
    "Ask anything, or reply to MediPlan AI..." if backend_ok else "Backend offline — chat disabled",
    disabled=not backend_ok
)

# Step 1: user typed something — show it immediately, then rerun
if user_input and not st.session_state.get("chat_pending_input"):
    st.session_state["chat_pending_msg"]   = user_input
    st.session_state["chat_pending_input"] = user_input
    st.rerun()

# Step 2: on the rerun where pending_input is set, actually call the backend
if st.session_state.get("chat_pending_input"):
    msg_to_send = st.session_state.pop("chat_pending_input")
    response, error = send_chat(user_id, msg_to_send)
    st.session_state["chat_pending_msg"] = None
    st.session_state["chat_error"] = error
    st.rerun()

# Quick starters
if not history:
    st.markdown("**Quick starters:**")
    cols = st.columns(3)
    starters = [
        "What should I study first today?",
        "Explain beta blockers simply",
        "5 high-yield Pharmacology mnemonics",
        "How much time do I have left?",
        "Quiz me on today's topic",
        "I'm overwhelmed — help me prioritise",
    ]
    for i,s in enumerate(starters):
        with cols[i%3]:
            if st.button(s, key=f"qs_{i}", use_container_width=True, disabled=not backend_ok):
                with st.spinner("Thinking..."):
                    response, error = send_chat(user_id, s)
                st.session_state["chat_error"] = error
                st.rerun()

# ── Schedule settings shortcut ─────────────────────────────────────────────────
st.markdown("---")
if st.button("⏰ Update today's study time", help="Change your study window for any day"):
    st.switch_page("pages/5_Schedule.py")
