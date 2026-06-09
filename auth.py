"""Authentication module using streamlit-authenticator."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st
import streamlit_authenticator as stauth

from config import SECRET_KEY, SESSION_TIMEOUT_MINUTES
from database import create_user, get_all_users_credentials, get_user_by_username

logger = logging.getLogger(__name__)

DEFAULT_USERS = [
    ("doctor1", "doctor123", "Doctor", "Dr. Rajesh Kumar", "doctor1@pvpi.local"),
    ("pharmacist1", "pharma123", "Pharmacist", "Pharmacist Priya Sharma", "pharmacist1@pvpi.local"),
    ("admin", "admin123", "Admin", "Admin User", "admin@pvpi.local"),
]


def hash_password(password: str) -> str:
    """Hash password using streamlit-authenticator bcrypt Hasher."""
    return stauth.Hasher.hash(password)


def seed_default_users() -> None:
    """Create default users if they do not exist."""
    for username, password, role, name, email in DEFAULT_USERS:
        existing = get_user_by_username(username)
        if not existing:
            create_user(username, hash_password(password), role, name, email)
            logger.info("Created default user: %s", username)


def get_authenticator() -> stauth.Authenticate:
    """Build and return streamlit-authenticator instance."""
    credentials = get_all_users_credentials()

    if not credentials["usernames"]:
        seed_default_users()
        credentials = get_all_users_credentials()

    authenticator = stauth.Authenticate(
        credentials,
        cookie_name="pvpi_auth_cookie",
        key=SECRET_KEY,
        cookie_expiry_days=1,
    )
    return authenticator


def check_session_timeout() -> bool:
    """Return True if session is still valid, False if expired."""
    last_activity = st.session_state.get("last_activity")
    if last_activity is None:
        return True

    timeout = timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    if datetime.now() - last_activity > timeout:
        return False
    return True


def update_activity() -> None:
    """Update last activity timestamp."""
    st.session_state.last_activity = datetime.now()


def get_user_role(username: str) -> Optional[str]:
    """Get role for authenticated user."""
    user = get_user_by_username(username)
    return user["role"] if user else None


def is_admin(username: str) -> bool:
    """Check if user has Admin role."""
    return get_user_role(username) == "Admin"


def is_authenticated() -> bool:
    """Check if user is currently authenticated."""
    return (
        st.session_state.get("authentication_status") is True
        and st.session_state.get("username") is not None
    )


def logout_user(authenticator: stauth.Authenticate) -> None:
    """Logout user and clear session."""
    authenticator.logout("Logout", "sidebar")
    for key in [
        "authentication_status",
        "username",
        "name",
        "role",
        "last_activity",
        "chatbot_state",
        "chat_messages",
        "adr_data",
        "current_step",
        "show_summary",
        "report_submitted",
        "submitted_report_id",
        "voice_text",
    ]:
        if key in st.session_state:
            del st.session_state[key]
