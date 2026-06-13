import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api import save_profile, generate_plan
from shared.db import init_db
from shared.syllabus import ALL_SUBJECTS
from datetime import date, timedelta

init_db()

st.markdown("## 🎯 Set up your study plan")
st.caption("No modes to choose — the system adapts automatically based on your exam date.")

with st.form("setup_form"):
    st.markdown("### 👤 About you")
    c1,c2 = st.columns(2)
    with c1: name = st.text_input("Your name", placeholder="Rajesh")
    with c2: exam_name = st.text_input("Exam", placeholder="NEET PG 2026")

    c3,c4 = st.columns(2)
    with c3:
        exam_date = st.date_input(
            "Exam date",
            value=date.today()+timedelta(days=45),
            min_value=date.today()+timedelta(days=1)
        )
        # Auto-show detected phase
        dr = (exam_date - date.today()).days
        if dr > 60:   phase_preview = "🐢 Marathon — deep coverage"
        elif dr > 14: phase_preview = "🏃 Sprint — high-yield focus"
        elif dr > 3:  phase_preview = "⚡ Crunch — triage mode"
        else:          phase_preview = "🚨 Emergency revision — rapid review"
        st.caption(f"System will auto-set: **{phase_preview}**")

    with c4:
        hours_per_day = st.slider("Hours available per day", 1.0, 12.0, 4.0, 0.5)

    st.markdown("### 📚 Subjects")
    subjects = st.multiselect("Select subjects", ALL_SUBJECTS,
                              default=["Pharmacology","Pathology","Medicine","Surgery"])
    weak_areas = st.multiselect("Weak areas (prioritised first)",
                                subjects if subjects else ALL_SUBJECTS)

    # ── Dynamic per-day schedule builder ─────────────────────────────────────
    st.markdown("### ⏰ Your weekly study schedule")
    st.caption(
        "Set the time window you're available each day. "
        "The AI will initiate a conversation at the **start of each window**. "
        "Leave a day blank if you're not studying that day."
    )

    DAYS = ["mon","tue","wed","thu","fri","sat","sun"]
    DAY_LABELS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

    schedule = {}
    cols = st.columns(7)
    for i, (day, label) in enumerate(zip(DAYS, DAY_LABELS)):
        with cols[i]:
            st.markdown(f"**{label[:3]}**")
            enabled = st.checkbox("On", key=f"en_{day}", value=(day not in ["sun"]))
            if enabled:
                start = st.time_input("Start", value=None, key=f"s_{day}", label_visibility="collapsed")
                end   = st.time_input("End",   value=None, key=f"e_{day}", label_visibility="collapsed")
                if start and end:
                    schedule[day] = [{"start": start.strftime("%H:%M"),
                                      "end":   end.strftime("%H:%M")}]

    submitted = st.form_submit_button("🚀 Generate my plan", type="primary", use_container_width=True)

if submitted:
    if not name or not subjects:
        st.error("Please fill in name and select subjects.")
    else:
        profile = {
            "name": name, "exam_name": exam_name,
            "exam_date": exam_date.isoformat(),
            "subjects": subjects, "weak_areas": weak_areas,
            "hours_per_day": hours_per_day,
            "schedule": schedule,
        }
        with st.spinner("Saving profile..."):
            save_profile(profile)
        with st.spinner(f"Generating your plan (phase: {phase_preview})..."):
            result = generate_plan()

        if result and not result.get("error"):
            st.success(f"✅ Plan generated — {result.get('tasks',0)} sessions · Phase: {result.get('phase','')}")
            st.balloons()
            if st.button("Go to my plan →", type="primary"):
                st.switch_page("pages/2_Study_Plan.py")
        else:
            st.error(result.get("error","Backend error — is FastAPI running?") if result else "Could not connect to backend")
