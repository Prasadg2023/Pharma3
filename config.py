"""Application configuration loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _secrets_file_exists() -> bool:
    """Check if a Streamlit secrets.toml file is present."""
    return any(
        path.exists()
        for path in (
            Path.home() / ".streamlit" / "secrets.toml",
            BASE_DIR / ".streamlit" / "secrets.toml",
        )
    )


def _get_config(key: str, default: str = "") -> str:
    """Read config from .env, then Streamlit secrets (cloud only)."""
    env_val = os.getenv(key)
    if env_val is not None and env_val != "":
        return env_val

    if _secrets_file_exists():
        try:
            import streamlit as st
            if key in st.secrets:
                return str(st.secrets[key])
        except Exception:
            pass

    return default


# SQLite database (no installation required)
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "pvpi_chatbot.db"

# SMTP
SMTP_EMAIL = _get_config("SMTP_EMAIL", "")
SMTP_PASSWORD = _get_config("SMTP_PASSWORD", "")
SMTP_RECEIVER = _get_config("SMTP_RECEIVER", "")
SMTP_HOST = _get_config("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_get_config("SMTP_PORT", "587"))

# Security
SECRET_KEY = _get_config("SECRET_KEY", "pvpi_default_secret_change_in_production")
SESSION_TIMEOUT_MINUTES = int(_get_config("SESSION_TIMEOUT_MINUTES", "30"))

# Paths
ASSETS_DIR = BASE_DIR / "assets"
REPORTS_DIR = BASE_DIR / "reports"
LOGO_PATH = ASSETS_DIR / "logo.png"

# Ensure data and reports directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Language codes for speech recognition
SPEECH_LANG_MAP = {
    "en": "en-IN",
    "hi": "hi-IN",
    "mr": "mr-IN",
}

# Total ADR workflow steps
TOTAL_STEPS = 18
