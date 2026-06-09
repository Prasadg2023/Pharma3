"""ADR reporting chatbot logic with validation and translation."""

import re
from datetime import datetime
from typing import Optional, Tuple

from deep_translator import GoogleTranslator
from langdetect import detect, LangDetectException

from config import TOTAL_STEPS
from translations import ADR_FIELDS, t

DATE_PATTERN = re.compile(r"^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})$")

GENDER_VALUES = {
    "en": ["male", "female", "other"],
    "hi": ["पुरुष", "महिला", "अन्य", "male", "female", "other"],
    "mr": ["पुरुष", "स्त्री", "इतर", "male", "female", "other"],
}

SERIOUS_VALUES = {
    "en": ["yes", "no"],
    "hi": ["हाँ", "हां", "नहीं", "yes", "no"],
    "mr": ["होय", "नाही", "yes", "no"],
}

OUTCOME_VALUES = {
    "en": ["recovered", "recovering", "not recovered", "fatal", "unknown"],
    "hi": ["ठीक", "ठीक हो रहा है", "ठीक नहीं हुआ", "घातक", "अज्ञात",
           "recovered", "recovering", "not recovered", "fatal", "unknown"],
    "mr": ["बरे", "बरे होत आहे", "बरे झाले नाही", "घातक", "अज्ञात",
           "recovered", "recovering", "not recovered", "fatal", "unknown"],
}

ROUTE_VALUES = {
    "en": ["oral", "iv", "im", "topical", "other"],
    "hi": ["मौखिक", "oral", "iv", "im", "त्वचा पर", "topical", "अन्य", "other"],
    "mr": ["तोंडी", "oral", "iv", "im", "त्वचेवर", "topical", "इतर", "other"],
}

ACTION_VALUES = {
    "en": ["stopped", "dose reduced", "dose increased", "no change", "unknown"],
    "hi": ["बंद", "खुराक कम", "खुराक बढ़ाई", "कोई परिवर्तन नहीं", "अज्ञात",
           "stopped", "dose reduced", "dose increased", "no change", "unknown"],
    "mr": ["थांबवले", "मात्रा कमी", "मात्रा वाढवली", "बदल नाही", "अज्ञात",
           "stopped", "dose reduced", "dose increased", "no change", "unknown"],
}

ONGOING_VALUES = ["ongoing", "चालू", "सुरू", "still ongoing", "अभी भी"]


def init_chatbot_state() -> None:
    """Initialize chatbot session state."""
    import streamlit as st

    defaults = {
        "current_step": 0,
        "adr_data": {},
        "chat_messages": [],
        "show_summary": False,
        "report_submitted": False,
        "submitted_report_id": None,
        "validation_error": None,
        "voice_text": "",
        "welcome_shown": False,
        "spoken_ids": set(),
        "pending_error": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def reset_chatbot() -> None:
    """Reset chatbot for a new report."""
    import streamlit as st

    st.session_state.current_step = 0
    st.session_state.adr_data = {}
    st.session_state.chat_messages = []
    st.session_state.show_summary = False
    st.session_state.report_submitted = False
    st.session_state.submitted_report_id = None
    st.session_state.validation_error = None
    st.session_state.voice_text = ""
    st.session_state.welcome_shown = False
    st.session_state.spoken_ids = set()
    st.session_state.pending_error = None


def get_current_question(lang: str) -> str:
    """Get the current question text."""
    step = _get_step()
    if step >= len(ADR_FIELDS):
        return ""
    _, question_key, _ = ADR_FIELDS[step]
    return t(question_key, lang)


def _get_step() -> int:
    import streamlit as st
    return st.session_state.get("current_step", 0)


def _normalize_value(value: str) -> str:
    return value.strip().lower()


def _parse_date(value: str) -> Optional[str]:
    """Parse and validate date, return DD/MM/YYYY format."""
    value = value.strip().lower()
    if value in [v.lower() for v in ONGOING_VALUES]:
        return "ongoing"

    match = DATE_PATTERN.match(value)
    if not match:
        return None

    day, month, year = match.groups()
    day, month = int(day), int(month)
    year = int(year)
    if year < 100:
        year += 2000

    try:
        dt = datetime(year, month, day)
        return dt.strftime("%d/%m/%Y")
    except ValueError:
        return None


def detect_and_translate(text: str, ui_lang: str) -> Tuple[str, str, str]:
    """
    Detect language and translate to English if needed.
    Returns (original, english_translation, detected_lang).
    """
    original = text.strip()
    if not original:
        return original, original, ui_lang

    detected = ui_lang
    try:
        detected = detect(original)
    except LangDetectException:
        detected = ui_lang

    if detected in ("hi", "mr") or ui_lang in ("hi", "mr"):
        try:
            translated = GoogleTranslator(source="auto", target="en").translate(original)
            return original, translated, detected
        except Exception:
            return original, original, detected

    return original, original, detected


def validate_response(value: str, step: int, lang: str) -> Tuple[bool, str, str]:
    """
    Validate user response for current step.
    Returns (is_valid, normalized_english_value, error_message).
    """
    value = value.strip()
    if not value:
        return False, "", t("val_required", lang)

    field_key, _, _ = ADR_FIELDS[step]
    original, english, _ = detect_and_translate(value, lang)

    if field_key == "patient_initial":
        if len(original.replace(" ", "")) != 1 or not original.replace(" ", "").isalpha():
            return False, "", t("val_initial", lang)
        return True, english.upper()[:1], ""

    if field_key == "age":
        try:
            age = float(original.replace(",", "."))
            if age < 0 or age > 150:
                return False, "", t("val_age", lang)
            return True, str(int(age)), ""
        except ValueError:
            return False, "", t("val_age", lang)

    if field_key == "gender":
        norm = _normalize_value(original)
        valid = GENDER_VALUES.get(lang, GENDER_VALUES["en"]) + GENDER_VALUES["en"]
        if norm not in [_normalize_value(v) for v in valid]:
            return False, "", t("val_gender", lang)
        gender_map = {
            "पुरुष": "Male", "male": "Male",
            "महिला": "Female", "स्त्री": "Female", "female": "Female",
            "अन्य": "Other", "इतर": "Other", "other": "Other",
        }
        return True, gender_map.get(norm, english.title()), ""

    if field_key == "weight":
        try:
            weight = float(original.replace(",", ".").replace("kg", "").strip())
            if weight < 0.1 or weight > 500:
                return False, "", t("val_weight", lang)
            return True, str(weight), ""
        except ValueError:
            return False, "", t("val_weight", lang)

    if field_key in ("reaction_start", "medicine_start"):
        parsed = _parse_date(original)
        if not parsed or parsed == "ongoing":
            return False, "", t("val_date", lang)
        return True, parsed, ""

    if field_key in ("reaction_stop", "medicine_stop"):
        parsed = _parse_date(original)
        if not parsed:
            return False, "", t("val_date_ongoing", lang)
        return True, parsed, ""

    if field_key == "reaction_description":
        if len(original) < 3:
            return False, "", t("val_required", lang)
        return True, english, ""

    if field_key == "serious":
        norm = _normalize_value(original)
        valid = SERIOUS_VALUES.get(lang, SERIOUS_VALUES["en"]) + SERIOUS_VALUES["en"]
        if norm not in [_normalize_value(v) for v in valid]:
            return False, "", t("val_serious", lang)
        yes_vals = ["yes", "हाँ", "हां", "होय"]
        return True, "Yes" if norm in yes_vals else "No", ""

    if field_key == "outcome":
        norm = _normalize_value(original)
        valid = OUTCOME_VALUES.get(lang, OUTCOME_VALUES["en"]) + OUTCOME_VALUES["en"]
        if norm not in [_normalize_value(v) for v in valid]:
            return False, "", t("val_outcome", lang)
        outcome_map = {
            "ठीक": "Recovered", "बरे": "Recovered", "recovered": "Recovered",
            "ठीक हो रहा है": "Recovering", "बरे होत आहे": "Recovering", "recovering": "Recovering",
            "ठीक नहीं हुआ": "Not Recovered", "बरे झाले नाही": "Not Recovered", "not recovered": "Not Recovered",
            "घातक": "Fatal", "fatal": "Fatal",
            "अज्ञात": "Unknown", "unknown": "Unknown",
        }
        return True, outcome_map.get(norm, english.title()), ""

    if field_key == "route":
        norm = _normalize_value(original)
        valid = ROUTE_VALUES.get(lang, ROUTE_VALUES["en"]) + ROUTE_VALUES["en"]
        if norm not in [_normalize_value(v) for v in valid]:
            return False, "", t("val_route", lang)
        route_map = {
            "मौखिक": "Oral", "तोंडी": "Oral", "oral": "Oral",
            "iv": "IV", "im": "IM",
            "त्वचा पर": "Topical", "त्वचेवर": "Topical", "topical": "Topical",
            "अन्य": "Other", "इतर": "Other", "other": "Other",
        }
        return True, route_map.get(norm, english.title()), ""

    if field_key == "action_taken":
        norm = _normalize_value(original)
        valid = ACTION_VALUES.get(lang, ACTION_VALUES["en"]) + ACTION_VALUES["en"]
        if norm not in [_normalize_value(v) for v in valid]:
            return False, "", t("val_action", lang)
        action_map = {
            "बंद": "Stopped", "थांबवले": "Stopped", "stopped": "Stopped",
            "खुराक कम": "Dose Reduced", "मात्रा कमी": "Dose Reduced", "dose reduced": "Dose Reduced",
            "खुराक बढ़ाई": "Dose Increased", "मात्रा वाढवली": "Dose Increased", "dose increased": "Dose Increased",
            "कोई परिवर्तन नहीं": "No Change", "बदल नाही": "No Change", "no change": "No Change",
            "अज्ञात": "Unknown", "unknown": "Unknown",
        }
        return True, action_map.get(norm, english.title()), ""

    # Default: medicine_name, dose, frequency, indication, reporter_name
    if len(original) < 1:
        return False, "", t("val_required", lang)
    return True, english, ""


def process_user_input(user_input: str, lang: str) -> Tuple[bool, Optional[str]]:
    """
    Process user input for current step.
    Returns (success, error_message).
    """
    import streamlit as st

    step = _get_step()
    if step >= TOTAL_STEPS:
        return False, None

    is_valid, normalized, error = validate_response(user_input, step, lang)
    if not is_valid:
        return False, error

    field_key, _, _ = ADR_FIELDS[step]
    original = user_input.strip()
    _, english, detected = detect_and_translate(original, lang)

    st.session_state.adr_data[field_key] = {
        "value_en": normalized,
        "value_original": original,
        "detected_language": detected,
    }

    st.session_state.chat_messages.append({"role": "user", "content": original})
    st.session_state.current_step += 1

    if st.session_state.current_step < TOTAL_STEPS:
        next_question = get_current_question(lang)
        st.session_state.chat_messages.append({"role": "assistant", "content": next_question})
    else:
        st.session_state.show_summary = True

    return True, None


def add_welcome_message(lang: str) -> None:
    """Add welcome message to chat if not already shown."""
    import streamlit as st

    if not st.session_state.get("welcome_shown"):
        welcome = t("welcome_message", lang)
        first_question = get_current_question(lang)
        st.session_state.chat_messages.append({"role": "assistant", "content": welcome})
        st.session_state.chat_messages.append({"role": "assistant", "content": first_question})
        st.session_state.welcome_shown = True


def get_progress() -> float:
    """Get progress as fraction 0.0 to 1.0."""
    import streamlit as st
    step = st.session_state.get("current_step", 0)
    if st.session_state.get("show_summary") or st.session_state.get("report_submitted"):
        return 1.0
    return min(step / TOTAL_STEPS, 1.0)


def build_report_payload(lang: str) -> dict:
    """Build final report payload for database storage."""
    import streamlit as st

    data = st.session_state.get("adr_data", {})
    payload = {
        "language": lang,
        "fields": {},
        "submitted_at": datetime.utcnow().isoformat(),
    }

    for field_key, _, label_key in ADR_FIELDS:
        field_data = data.get(field_key, {})
        payload["fields"][field_key] = {
            "label": t(label_key, "en"),
            "value_en": field_data.get("value_en", ""),
            "value_original": field_data.get("value_original", ""),
            "detected_language": field_data.get("detected_language", lang),
        }

    return payload


def get_reporter_name() -> str:
    """Extract reporter name from ADR data."""
    import streamlit as st
    data = st.session_state.get("adr_data", {})
    reporter = data.get("reporter_name", {})
    return reporter.get("value_en", reporter.get("value_original", "Unknown"))
