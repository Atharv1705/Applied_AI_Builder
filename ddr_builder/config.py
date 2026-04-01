import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Gemini: use GEMINI_API_KEY or common alias GOOGLE_API_KEY
GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")).strip()
# Default works with current AI Studio model list; override in .env if needed.
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
