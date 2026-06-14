import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api import get_profile, get_plan, get_progress, health_check
from frontend.session import get_user_id
from shared.db import init_db
from datetime import date

st.set_page_config(
    page_title="MediPlan AI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()
user_id = get_user_id()

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap');
html,body,[class*="css"]{font-family:'Inter',sans-serif}
.stApp{background:#0F1117}
section[data-testid="stSidebar"]{background:#161B27!important;border-right:1px solid #1E2535}
.mp-card{background:#161B27;border:1px solid #1E2535;border-radius:12px;padding:1.25rem 1.5rem;margin-bottom:12px}
.mp-label{font-size:11px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:#4A5568;margin-bottom:4px}
.mp-value{font-size:28px;font-weight:600;color:#E2E8F0}
.mp-sub{font-size:12px;color:#4A5568;margin-top:2px}
.pb-bg{background:#1E2535;border-radius:4px;height:6px;overflow:hidden;margin:6px 0}
.pb-fill{height:6px;border-radius:4px;background:linear-gradient(90deg,#2563EB,#7C3AED)}
.task-card{background:#161B27;border:1px solid #1E2535;border-radius:10px;padding:10px 14px;margin-bottom:6px;display:flex;align-items:center;gap:10px}
.phase-badge{font-size:11px;padding:3px 10px;border-radius:20px;font-weight:500}
.badge-marathon{background:#1B2D1B;color:#86EFAC;border:1px solid #14532D}
.badge-sprint{background:#1B1F2D;color:#93C5FD;border:1px solid #1E3A5F}
.badge-crunch{background:#2D2A1B;color:#FDE68A;border:1px solid #78350F}
.badge-emergency{background:#2D1B1B;color:#FCA5A5;border:1px solid #7F1D1D}
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🩺 MediPlan AI")
    st.caption("Proactive MBBS study companion")

    backend_ok = health_check()
    if backend_ok:
        st.success("⚡ Scheduler running", icon=None)
    else:
        st.warning("⚠ Backend offline — start with `uvicorn backend.main:app`")

    profile = get_profile(user_id)
    if profile:
        from datetime import datetime
        try:
            dr = max((datetime.strptime(profile["exam_date"],"%Y-%m-%d").date() - date.today()).days, 0)
        except Exception:
            dr = "?"

        from shared.db import detect_phase
        phase = detect_phase(profile.get("exam_date",""))
        badge = f"badge-{phase}"
        label = {"marathon":"🐢 Marathon","sprint":"🏃 Sprint","crunch":"⚡ Crunch","emergency":"🚨 Emergency"}[phase]

        st.markdown(f"""
        <div class='mp-card'>
            <div class='mp-label'>Exam countdown</div>
            <div class='mp-value'>{dr}</div>
            <div class='mp-sub'>days to {profile.get("exam_name","")}</div>
            <div style='margin-top:8px'><span class='phase-badge {badge}'>{label}</span></div>
        </div>""", unsafe_allow_html=True)

        prog = get_progress(user_id)
        total = prog.get("total",0); done = prog.get("done",0)
        pct = round(done/total*100) if total else 0
        st.markdown(f"""
        <div class='mp-card'>
            <div class='mp-label'>Progress</div>
            <div class='mp-value'>{pct}%</div>
            <div class='pb-bg'><div class='pb-fill' style='width:{pct}%'></div></div>
            <div class='mp-sub'>{done}/{total} topics done</div>
        </div>""", unsafe_allow_html=True)
    else:
        st.info("👋 Set up your profile to get started")

# ── Main ──────────────────────────────────────────────────────────────────────
profile = get_profile(user_id)

if not profile:
    st.markdown("## 👋 Welcome to MediPlan AI")
    st.markdown("The proactive study companion that reaches out to you — not the other way around.")
    col1,col2,col3 = st.columns(3)
    for col,icon,title,desc in [
        (col1,"📚","RAG-powered","Study plan built on the actual CBME syllabus"),
        (col2,"🤖","Proactive AI","AI initiates study sessions at your scheduled times"),
        (col3,"🔄","Adaptive plans","Phase auto-adjusts as your exam gets closer — silently"),
    ]:
        with col:
            st.markdown(f"<div class='mp-card'><div style='font-size:24px'>{icon}</div><div style='font-size:14px;font-weight:500;color:#E2E8F0;margin:6px 0'>{title}</div><div style='font-size:12px;color:#4A5568'>{desc}</div></div>", unsafe_allow_html=True)
    if st.button("🚀 Get started →", type="primary", use_container_width=True):
        st.switch_page("pages/1_Setup.py")
else:
    st.markdown(f"## Hey {profile['name']} 👋")
    from shared.db import detect_phase
    phase = detect_phase(profile["exam_date"])

    today_str = date.today().isoformat()
    tasks = get_plan(user_id, today_str)
    pending = [t for t in tasks if t["status"]=="pending"]
    done_t  = [t for t in tasks if t["status"]=="done"]

    col1,col2,col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='mp-card'><div class='mp-label'>Today</div><div class='mp-value'>{len(tasks)}</div><div class='mp-sub'>{len(done_t)} done · {len(pending)} pending</div></div>", unsafe_allow_html=True)
    with col2:
        mins = sum(t.get("duration_mins",60) for t in pending)
        st.markdown(f"<div class='mp-card'><div class='mp-label'>Study time left</div><div class='mp-value'>{mins//60}h {mins%60}m</div><div class='mp-sub'>across {len(pending)} topics</div></div>", unsafe_allow_html=True)
    with col3:
        subjs = list(set(t["subject"] for t in tasks))
        st.markdown(f"<div class='mp-card'><div class='mp-label'>Subjects today</div><div class='mp-value'>{len(subjs)}</div><div class='mp-sub'>{', '.join(subjs[:2])}</div></div>", unsafe_allow_html=True)

    st.markdown("### Today's sessions")
    for t in tasks[:8]:
        done_icon = "✅" if t["status"]=="done" else "📖"
        fade = "opacity:0.45;" if t["status"]=="done" else ""
        st.markdown(f"""<div class='task-card' style='{fade}'>
            <span style='font-size:18px'>{done_icon}</span>
            <div>
                <div style='font-size:14px;font-weight:500;color:#E2E8F0'>{t["subject"]} — {t["topic"]}</div>
                <div style='font-size:11px;color:#4A5568'>{t.get("duration_mins",60)} mins</div>
            </div></div>""", unsafe_allow_html=True)

    c1,c2 = st.columns(2)
    with c1:
        if st.button("📋 Study plan",use_container_width=True): st.switch_page("pages/2_Study_Plan.py")
    with c2:
        if st.button("💬 Study chat",use_container_width=True): st.switch_page("pages/4_Study_Chat.py")
