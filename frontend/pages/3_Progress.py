import streamlit as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api import get_profile, get_progress
from frontend.session import get_user_id

user_id = get_user_id()
import plotly.graph_objects as go
from datetime import date, datetime

profile = get_profile(user_id)
if not profile:
    st.warning("Set up your profile first.")
    st.stop()

st.markdown("## 📊 Progress")

prog = get_progress(user_id)
total = prog.get("total",0); done = prog.get("done",0)
pct   = round(done/total*100,1) if total else 0
dr    = prog.get("days_remaining",0)
phase = prog.get("phase","sprint")
per_day = round((total-done)/max(dr,1),1)

c1,c2,c3,c4 = st.columns(4)
for col,label,val,sub,red in [
    (c1,"Completion",f"{pct}%",f"{done}/{total} topics",False),
    (c2,"Days left",str(dr),f"to {profile.get('exam_name','')}",False),
    (c3,"Phase",phase.title(),"auto-detected",False),
    (c4,"Topics/day needed",str(per_day),"to finish on time", per_day>5),
]:
    with col:
        color = "#F87171" if red else "#E2E8F0"
        st.markdown(f"""<div style='background:#161B27;border:1px solid #1E2535;border-radius:12px;padding:1rem 1.25rem'>
        <div style='font-size:10px;color:#4A5568;text-transform:uppercase;letter-spacing:.08em'>{label}</div>
        <div style='font-size:28px;font-weight:600;color:{color}'>{val}</div>
        <div style='font-size:11px;color:#4A5568'>{sub}</div>
        </div>""", unsafe_allow_html=True)

by_subj = prog.get("by_subject",[])
if by_subj:
    labels = [s["subject"] for s in by_subj]
    dones  = [s["done"] for s in by_subj]
    totals = [s["total"] for s in by_subj]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Done",x=labels,y=dones,marker_color="#3B82F6"))
    fig.add_trace(go.Bar(name="Left",x=labels,y=[t-d for t,d in zip(totals,dones)],marker_color="#1E2535"))
    fig.update_layout(barmode="stack",plot_bgcolor="#0F1117",paper_bgcolor="#0F1117",
                      font_color="#CBD5E1",height=300,margin=dict(l=10,r=10,t=20,b=10))
    fig.update_xaxes(gridcolor="#1E2535"); fig.update_yaxes(gridcolor="#1E2535")
    st.plotly_chart(fig,use_container_width=True)

    for s in sorted(by_subj,key=lambda x:x["done"]/x["total"] if x["total"] else 0):
        p = round(s["done"]/s["total"]*100) if s["total"] else 0
        c = "#F87171" if p<30 else "#FBBF24" if p<70 else "#86EFAC"
        st.markdown(f"""<div style='background:#161B27;border:1px solid #1E2535;border-radius:8px;padding:9px 14px;margin-bottom:5px;display:flex;align-items:center;gap:12px'>
        <div style='flex:1;font-size:13px;color:#E2E8F0'>{s["subject"]}</div>
        <div style='width:180px;background:#0F1117;border-radius:3px;height:5px;overflow:hidden'><div style='width:{p}%;height:5px;background:{c};border-radius:3px'></div></div>
        <div style='font-size:12px;color:{c};min-width:36px;text-align:right'>{p}%</div>
        <div style='font-size:11px;color:#4A5568;min-width:55px;text-align:right'>{s["done"]}/{s["total"]}</div>
        </div>""", unsafe_allow_html=True)
