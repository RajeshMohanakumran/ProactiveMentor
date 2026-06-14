"""
Per-session user identity for MediPlan AI.

Each browser session gets a random user_id, stored in the URL as ?uid=...
so it persists across page reloads and navigation between Streamlit pages
(query params survive st.switch_page and browser refresh, unlike
st.session_state which resets on full reload).

This is what makes the deployed app multi-tenant: every visitor gets their
own isolated profile, plan, and chat history, scoped by this user_id.
"""
import uuid
import streamlit as st


def get_user_id() -> str:
    """
    Returns a stable per-browser-session user_id.
    Generates a new one on first visit and stores it in the URL query params.
    """
    qp = st.query_params
    uid = qp.get("uid")

    if not uid:
        uid = uuid.uuid4().hex[:16]
        st.query_params["uid"] = uid

    return uid
