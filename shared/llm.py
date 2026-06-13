"""
LLM client — used by both FastAPI backend and Streamlit frontend.
Groq primary, Gemini Flash fallback.
"""
import os, time
from pathlib import Path

# Load .env so FastAPI (which doesn't have st.secrets) gets the keys too
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except Exception:
    pass

GROQ_MODEL      = "llama-3.3-70b-versatile"
GROQ_MODEL_FAST = "llama-3.1-8b-instant"
GEMINI_MODEL    = "gemini-2.0-flash"


def _groq_key() -> str:
    # Try streamlit secrets first, then env var
    try:
        import streamlit as st
        return st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY", "")
    except Exception:
        return os.getenv("GROQ_API_KEY", "")


def _gemini_key() -> str:
    try:
        import streamlit as st
        return st.secrets.get("GEMINI_API_KEY") or os.getenv("GEMINI_API_KEY", "")
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")


def llm_call(system: str, user: str,
             temperature: float = 0.7,
             max_tokens: int = 1024,
             fast: bool = False) -> str:
    """Groq first, Gemini fallback. fast=True uses 8B model.

    Note: default max_tokens kept small (1024) because requesting too many
    output tokens from llama-3.1-8b-instant causes Groq to return
    413 Payload Too Large. Planner calls explicitly pass max_tokens=8192
    since they use the 70B model with a much larger context."""
    model = GROQ_MODEL_FAST if fast else GROQ_MODEL
    key   = _groq_key()

    if key:
        try:
            from groq import Groq
            resp = Groq(api_key=key).chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return resp.choices[0].message.content
        except Exception as e:
            err = str(e).lower()
            if not any(k in err for k in ("rate", "decommission", "model", "429", "413", "too large", "payload")):
                raise

    # Gemini fallback
    gkey = _gemini_key()
    if gkey:
        import google.generativeai as genai
        genai.configure(api_key=gkey)
        resp = genai.GenerativeModel(GEMINI_MODEL).generate_content(
            f"{system}\n\n{user}"
        )
        return resp.text

    raise RuntimeError("No API key found. Set GROQ_API_KEY in env or .streamlit/secrets.toml")


def llm_stream(system: str, user: str, temperature: float = 0.7):
    """Streaming for Streamlit chat UI."""
    key = _groq_key()
    if key:
        try:
            from groq import Groq
            stream = Groq(api_key=key).chat.completions.create(
                model=GROQ_MODEL_FAST,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                temperature=temperature,
                max_tokens=2048,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            return
        except Exception as e:
            if not any(k in str(e).lower() for k in ("rate", "decommission", "429")):
                raise

    # Gemini non-streaming fallback
    gkey = _gemini_key()
    if gkey:
        import google.generativeai as genai
        genai.configure(api_key=gkey)
        text = genai.GenerativeModel(GEMINI_MODEL).generate_content(
            f"{system}\n\n{user}"
        ).text
        for word in text.split(" "):
            yield word + " "
            time.sleep(0.01)