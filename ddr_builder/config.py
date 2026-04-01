import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get_api_key() -> str:
    # 1. Environment variable / .env file
    key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")).strip()
    if key:
        return key
    # 2. Streamlit secrets (when deployed on Streamlit Cloud)
    try:
        import streamlit as st
        key = (st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY", "")).strip()
    except Exception:
        pass
    return key


GEMINI_API_KEY = _get_api_key()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

CHUNK_MAX_CHARS = int(os.getenv("CHUNK_MAX_CHARS", "12000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "400"))


def require_gemini_key() -> None:
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) is not set. "
            "Copy .env.example to .env and add your Google AI / Gemini API key."
        )


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent
