"""
Standalone schedule editor — student can update any day's study window
without going through full setup again. Changes take effect in the
backend scheduler within the next 1-minute check cycle.
"""
import streamlit as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.api import get_profile, update_schedule
from frontend.session import get_user_id

user_id = get_user_id()
profile = get_profile(user_id)
if not profile:
    st.warning("Set up your profile first.")
    st.stop()

st.markdown("## ⏰ Weekly Study Schedule")
st.caption(
    "Update your study windows anytime. "
    "The backend scheduler reads this every 5 minutes — "
    "changes take effect at the next check cycle."
)

DAYS = ["mon","tue","wed","thu","fri","sat","sun"]
LABELS = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]

existing = profile.get("schedule", {})

new_schedule = {}
st.markdown("### Set your windows")

for day, label in zip(DAYS, LABELS):
    col1, col2, col3 = st.columns([2, 2, 1])
    existing_slot = existing.get(day, [{}])[0] if existing.get(day) else {}
    with col1:
        enabled = st.checkbox(label, key=f"en_{day}",
                              value=bool(existing_slot))
    with col2:
        if enabled:
            import datetime as dtmod
            default_start = dtmod.time(18, 0)
            default_end   = dtmod.time(20, 0)
            if existing_slot.get("start"):
                try:
                    h,m = map(int, existing_slot["start"].split(":"))
                    default_start = dtmod.time(h,m)
                except Exception:
                    pass
            if existing_slot.get("end"):
                try:
                    h,m = map(int, existing_slot["end"].split(":"))
                    default_end = dtmod.time(h,m)
                except Exception:
                    pass
            start = st.time_input(f"Start", value=default_start, key=f"s_{day}")
            end   = st.time_input(f"End",   value=default_end,   key=f"e_{day}")
            if start and end:
                new_schedule[day] = [{"start": start.strftime("%H:%M"),
                                      "end":   end.strftime("%H:%M")}]
    with col3:
        if enabled and day in new_schedule:
            st.markdown(f"<div style='font-size:11px;color:#4A5568;padding-top:32px'>"
                        f"{new_schedule[day][0]['start']} – {new_schedule[day][0]['end']}</div>",
                        unsafe_allow_html=True)

st.markdown("---")

# Today override
st.markdown("### ⚡ Today override")
st.caption("Studying at an unusual time today? Override just today's window.")
import datetime as dtmod
today_key = dtmod.datetime.now().strftime("%a").lower()

c1,c2 = st.columns(2)
with c1: override_start = st.time_input("Today starts", value=dtmod.time(18,0))
with c2: override_end   = st.time_input("Today ends",   value=dtmod.time(20,0))

col_save1, col_save2 = st.columns(2)
with col_save1:
    if st.button("💾 Save weekly schedule", type="primary", use_container_width=True):
        res = update_schedule(user_id, new_schedule)
        if res and "_error" not in res:
            st.success("Schedule saved — scheduler will pick this up in the next cycle.")
        else:
            st.error(f"⚠ {res.get('_error','Unknown error') if res else 'Could not save.'}")

with col_save2:
    if st.button("⚡ Apply today override", use_container_width=True):
        today_schedule = dict(existing)
        today_schedule[today_key] = [{
            "start": override_start.strftime("%H:%M"),
            "end":   override_end.strftime("%H:%M"),
        }]
        res = update_schedule(user_id, today_schedule)
        if res and "_error" not in res:
            st.success(f"Today's window updated to {override_start.strftime('%H:%M')} – {override_end.strftime('%H:%M')}. Active in next scheduler cycle.")
        else:
            st.error(f"⚠ {res.get('_error','Unknown error') if res else 'Backend not reachable.'}")
