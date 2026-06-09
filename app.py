"""
PvPI ADR Reporting Chatbot
Pharmacovigilance Programme of India - Adverse Drug Reaction Reporting
"""

import streamlit as st

st.set_page_config(
    page_title="PvPI ADR Reporting Chatbot",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded",
)

import logging
from pathlib import Path

from auth import (
    check_session_timeout,
    get_authenticator,
    get_user_role,
    is_authenticated,
    logout_user,
    update_activity,
)
from chatbot import (
    add_welcome_message,
    build_report_payload,
    get_progress,
    get_reporter_name,
    init_chatbot_state as chatbot_init,
    process_user_input,
    reset_chatbot,
)
from config import LOGO_PATH, TOTAL_STEPS
from database import init_database, save_adr_report
from email_service import send_adr_report_email
from pdf_generator import generate_adr_pdf, get_pdf_bytes
from translations import ADR_FIELDS, LANGUAGE_OPTIONS, t
from voice_service import (
    clear_spoken_cache,
    get_question_to_speak,
    render_voice_answer,
    speak_text,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom CSS for healthcare theme
st.markdown(
    """
    <style>
    .main-header {
        background: linear-gradient(135deg, #005293 0%, #0077b6 100%);
        padding: 1.5rem 2rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { color: white !important; margin: 0; font-size: 1.8rem; }
    .main-header p { color: #e0f0ff !important; margin: 0.3rem 0 0 0; }
    .stChatMessage { border-radius: 10px; }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #f8fbff 0%, #eef5fc 100%);
    }
    .progress-text { font-size: 0.9rem; color: #005293; font-weight: 600; }
    .summary-card {
        background: #f0f7ff;
        border-left: 4px solid #005293;
        padding: 1rem;
        border-radius: 0 8px 8px 0;
        margin: 0.5rem 0;
    }
  </style>
    """,
    unsafe_allow_html=True,
)


def init_session():
    """Initialize all session state."""
    if "language" not in st.session_state:
        st.session_state.language = "en"
    chatbot_init()


def render_sidebar(lang: str, authenticator):
    """Render sidebar with logo, language, user info, and progress."""
    with st.sidebar:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=180)
        else:
            st.markdown("### 💊 PvPI")

        st.markdown("---")
        st.subheader(t("sidebar_language", lang))
        selected_lang = st.selectbox(
            t("sidebar_language", lang),
            options=list(LANGUAGE_OPTIONS.keys()),
            format_func=lambda x: LANGUAGE_OPTIONS[x],
            index=list(LANGUAGE_OPTIONS.keys()).index(st.session_state.language),
            label_visibility="collapsed",
        )
        if selected_lang != st.session_state.language:
            st.session_state.language = selected_lang
            st.rerun()

        st.markdown("---")

        if is_authenticated():
            username = st.session_state.get("username", "")
            name = st.session_state.get("name", username)
            role = st.session_state.get("role") or get_user_role(username)

            st.markdown(f"**{t('sidebar_user', lang)}:** {name}")
            st.markdown(f"**{t('sidebar_role', lang)}:** {role}")

            st.markdown("---")
            st.subheader(t("sidebar_progress", lang))
            progress = get_progress()
            current_step = st.session_state.get("current_step", 0)
            if st.session_state.get("show_summary") or st.session_state.get("report_submitted"):
                step_display = TOTAL_STEPS
            else:
                step_display = min(current_step + 1, TOTAL_STEPS)

            st.progress(progress)
            st.markdown(
                f'<p class="progress-text">{t("sidebar_step", lang, current=step_display, total=TOTAL_STEPS)}</p>',
                unsafe_allow_html=True,
            )

            st.markdown("---")
            if st.button(t("sidebar_new_report", lang), use_container_width=True):
                reset_chatbot()
                clear_spoken_cache()
                st.rerun()

            authenticator.logout(t("sidebar_logout", lang), "sidebar")


def render_login(lang: str, authenticator):
    """Render login form."""
    st.markdown(
        f"""
        <div class="main-header">
            <h1>{t("app_title", lang)}</h1>
            <p>{t("app_subtitle", lang)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader(t("login_title", lang))
        st.caption(t("login_subtitle", lang))

        try:
            authenticator.login(location="main", key="pvpi_login")
        except Exception as e:
            logger.error("Login error: %s", e)
            st.error(t("login_failed", lang))

        if st.session_state.get("authentication_status") is False:
            st.error(t("login_failed", lang))
        elif st.session_state.get("authentication_status") is True:
            username = st.session_state.username
            st.session_state.role = get_user_role(username)
            update_activity()
            st.success(t("login_success", lang))
            st.rerun()


def render_summary(lang: str, username: str):
    """Render ADR report summary and submission."""
    st.subheader(t("summary_title", lang))
    st.caption(t("summary_subtitle", lang))

    adr_data = st.session_state.get("adr_data", {})

    for field_key, _, label_key in ADR_FIELDS:
        field = adr_data.get(field_key, {})
        label = t(label_key, lang)
        value_en = field.get("value_en", "")
        value_orig = field.get("value_original", "")

        with st.expander(f"**{label}**: {value_orig or value_en}", expanded=False):
            st.markdown(f"**{t('summary_original', lang)}:** {value_orig}")
            if value_orig != value_en:
                st.markdown(f"**{t('summary_translated', lang)}:** {value_en}")
                st.caption(t("translation_note", lang))

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("edit_report", lang), use_container_width=True):
            st.session_state.show_summary = False
            step = len(ADR_FIELDS) - 1
            st.session_state.current_step = step
            st.rerun()

    with col2:
        if st.button(t("confirm_submit", lang), type="primary", use_container_width=True):
            with st.spinner("Submitting report..."):
                payload = build_report_payload(lang)
                reporter = get_reporter_name()

                report_id = save_adr_report(
                    report_data=payload,
                    language=lang,
                    reporter_name=reporter,
                    submitted_by=username,
                )

                if report_id:
                    pdf_path = generate_adr_pdf(payload, report_id, reporter, lang)
                    send_adr_report_email(report_id, reporter, pdf_path, lang)

                    st.session_state.report_submitted = True
                    st.session_state.submitted_report_id = report_id
                    st.session_state.pdf_path = str(pdf_path)
                    st.rerun()
                else:
                    st.error(t("error_db", lang))


def render_submitted(lang: str):
    """Render post-submission view with PDF download."""
    report_id = st.session_state.get("submitted_report_id")
    st.success(t("report_submitted", lang))
    st.info(f"**{t('report_id_label', lang)}:** {report_id}")

    pdf_path = st.session_state.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        pdf_bytes = get_pdf_bytes(Path(pdf_path))
        st.download_button(
            label=t("download_pdf", lang),
            data=pdf_bytes,
            file_name=Path(pdf_path).name,
            mime="application/pdf",
            use_container_width=True,
        )

    if st.button(t("start_new", lang), use_container_width=True):
        reset_chatbot()
        st.rerun()


def render_chatbot(lang: str):
    """Render voice-first chatbot: bot speaks questions, user answers by voice."""
    st.markdown(
        f"""
        <div class="main-header">
            <h1>{t("app_title", lang)}</h1>
            <p>{t("app_subtitle", lang)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"📚 {t('college_disclaimer', lang)}")

    if st.session_state.get("report_submitted"):
        render_submitted(lang)
        return

    if st.session_state.get("show_summary"):
        render_summary(lang, st.session_state.username)
        return

    add_welcome_message(lang)

    # --- Current question (bot speaks this aloud) ---
    question_text, speech_key = get_question_to_speak(lang)
    speak_text(question_text, lang, key=speech_key)

    st.markdown("---")
    st.subheader(f"🗣️ {t('voice_mode_title', lang)}")

    col_listen, col_repeat = st.columns([4, 1])
    with col_listen:
        st.info(f"**{t('assistant_label', lang)}:** {question_text}")
        st.caption(t("voice_bot_asks", lang))
    with col_repeat:
        if st.button(t("voice_repeat", lang), use_container_width=True):
            repeat_key = speech_key + "_repeat"
            st.session_state.spoken_ids.discard(repeat_key)
            speak_text(question_text, lang, key=repeat_key)
            st.rerun()

    # Chat history (compact)
    with st.expander("💬 Conversation history", expanded=False):
        for message in st.session_state.get("chat_messages", []):
            role = "assistant" if message["role"] == "assistant" else "user"
            label = t("assistant_label", lang) if role == "assistant" else t("user_label", lang)
            st.markdown(f"**{label}:** {message['content']}")

    if st.session_state.get("pending_error"):
        err = st.session_state.pending_error
        st.warning(err)
        speak_text(err, lang, key=f"validation_{st.session_state.current_step}")

    # --- Voice answer (primary) ---
    st.markdown("---")
    st.caption(t("voice_you_answer", lang))

    transcribed = render_voice_answer(lang, t("voice_start", lang))

    if transcribed:
        st.success(f"✅ {t('voice_heard', lang)}: **{transcribed}**")
        success, error = process_user_input(transcribed, lang)
        if not success:
            st.session_state.pending_error = error
        else:
            st.session_state.pending_error = None
        st.rerun()

    # --- Optional text fallback ---
    with st.expander(t("type_instead", lang), expanded=False):
        user_input = st.text_input(
            t("chat_placeholder", lang),
            key=f"text_fallback_{st.session_state.get('current_step', 0)}",
        )
        if st.button(t("submit_answer", lang), key=f"submit_text_{st.session_state.current_step}"):
            if user_input:
                success, error = process_user_input(user_input, lang)
                if not success:
                    st.session_state.pending_error = error
                else:
                    st.session_state.pending_error = None
                st.rerun()
            else:
                st.warning(t("val_required", lang))


def main():
    """Main application entry point."""
    init_session()
    lang = st.session_state.language

    try:
        init_database()
    except Exception as e:
        st.error(t("error_db", lang))
        st.code(str(e))
        st.stop()

    authenticator = get_authenticator()

    if not check_session_timeout() and is_authenticated():
        logout_user(authenticator)
        st.warning(t("session_expired", lang))
        st.rerun()

    render_sidebar(lang, authenticator)

    if not is_authenticated():
        render_login(lang, authenticator)
        return

    update_activity()

    if "role" not in st.session_state or not st.session_state.role:
        st.session_state.role = get_user_role(st.session_state.username)

    render_chatbot(lang)


if __name__ == "__main__":
    main()
