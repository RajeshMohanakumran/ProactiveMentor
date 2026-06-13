import streamlit as st
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api import get_profile, get_plan, mark_task, replan
from datetime import date, timedelta

profile = get_profile()
if not profile:
    st.warning("Set up your profile first.")
    if st.button("Go to setup"): st.switch_page("pages/1_Setup.py")
    st.stop()

st.markdown("## 📋 Study Plan")

view = st.radio("View", ["Today","This week","All"], horizontal=True)
col_r, = st.columns([1])
if st.button("🔄 Fell behind? Replan"):
    with st.spinner("Replanning..."):
        res = replan()
    if res:
        st.success(f"Plan updated! {res.get('proactive_msg','')}")
        st.rerun()

today = date.today()
if view == "Today":
    tasks = get_plan(today.isoformat())
elif view == "This week":
    all_t = get_plan()
    tasks = [t for t in all_t if today.isoformat() <= t["plan_date"] <= (today+timedelta(7)).isoformat()]
else:
    tasks = get_plan()

if not tasks:
    st.info("No tasks yet. Generate your plan from Setup.")
    st.stop()

from itertools import groupby
grouped = {k:list(v) for k,v in groupby(sorted(tasks,key=lambda x:x["plan_date"]),key=lambda x:x["plan_date"])}

pcols = {"high":"#F87171","medium":"#FBBF24","low":"#93C5FD"}

for day_str, day_tasks in grouped.items():
    d = date.fromisoformat(day_str)
    label = "📅 Today" if d==today else f"📅 {d.strftime('%A, %d %b')}"
    done_c = sum(1 for t in day_tasks if t["status"]=="done")
    with st.expander(f"{label}  —  {done_c}/{len(day_tasks)} done", expanded=(day_str==today.isoformat())):
        for t in day_tasks:
            ca,cb,cc = st.columns([4,1,1])
            is_done = t["status"]=="done"
            color = pcols.get(t.get("priority","medium"),"#FBBF24")
            with ca:
                st.markdown(f"""<div style='opacity:{"0.4" if is_done else "1"}'>
                    <span style='color:{color};font-size:11px;font-weight:500;text-transform:uppercase;letter-spacing:.06em'>{t.get("priority","med")} · {t.get("session_type","learn")}</span><br>
                    <span style='font-size:14px;font-weight:500;color:#E2E8F0'>{t["subject"]} — {t["topic"]}</span><br>
                    <span style='font-size:11px;color:#4A5568'>{t.get("duration_mins",60)} mins</span>
                </div>""", unsafe_allow_html=True)
                if t.get("subtopics"):
                    st.caption("Covers: " + " · ".join(t["subtopics"][:3]))
            with cb:
                if not is_done:
                    if st.button("✅", key=f"d_{t['id']}"):
                        mark_task(t["id"],"done"); st.rerun()
                else:
                    st.markdown("<span style='color:#22C55E'>✓</span>",unsafe_allow_html=True)
            with cc:
                if st.button("⏭", key=f"s_{t['id']}"):
                    mark_task(t["id"],"skipped"); st.rerun()
