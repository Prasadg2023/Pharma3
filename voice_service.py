"""Voice interaction: text-to-speech for questions, speech-to-text for answers."""

import hashlib
import json

import streamlit as st
import streamlit.components.v1 as components
from streamlit_mic_recorder import speech_to_text

from config import SPEECH_LANG_MAP

TTS_LANG_MAP = {
    "en": "en-IN",
    "hi": "hi-IN",
    "mr": "mr-IN",
}


def _speech_key(text: str, lang: str) -> str:
    return hashlib.md5(f"{lang}:{text}".encode()).hexdigest()[:12]


def speak_text(text: str, lang: str = "en", key: str = "") -> None:
    """Speak text aloud using browser Web Speech API. Speaks once per unique key."""
    if not text or not text.strip():
        return

    speech_id = key or _speech_key(text, lang)
    spoken_set = st.session_state.setdefault("spoken_ids", set())

    if speech_id in spoken_set:
        return

    spoken_set.add(speech_id)
    tts_lang = TTS_LANG_MAP.get(lang, "en-IN")
    safe_text = json.dumps(text)

    components.html(
        f"""
        <script>
        (function() {{
            const msg = {safe_text};
            const synth = window.speechSynthesis;
            if (!synth) return;
            synth.cancel();
            const utter = new SpeechSynthesisUtterance(msg);
            utter.lang = "{tts_lang}";
            utter.rate = 0.92;
            utter.pitch = 1;
            const pickVoice = () => {{
                const voices = synth.getVoices();
                const match = voices.find(v => v.lang.startsWith("{tts_lang[:2]}"));
                if (match) utter.voice = match;
                synth.speak(utter);
            }};
            if (synth.getVoices().length) pickVoice();
            else synth.onvoiceschanged = pickVoice;
        }})();
        </script>
        """,
        height=0,
    )


def clear_spoken_cache() -> None:
    """Clear TTS cache when starting a new report."""
    st.session_state.spoken_ids = set()


def render_voice_answer(lang: str, prompt_label: str) -> str | None:
    """Render microphone for voice answer. Returns transcribed text or None."""
    speech_lang = SPEECH_LANG_MAP.get(lang, "en-IN")

    st.markdown(f"### 🎤 {prompt_label}")
    transcribed = speech_to_text(
        language=speech_lang,
        start_prompt="🎙️ " + prompt_label,
        stop_prompt="⏹ Stop",
        just_once=True,
        key=f"voice_answer_{lang}_{st.session_state.get('current_step', 0)}",
        use_container_width=True,
    )

    return transcribed if transcribed else None


def get_question_to_speak(lang: str) -> tuple[str, str]:
    """Return (text_to_speak, speech_key) for current assistant message."""
    from chatbot import get_current_question

    messages = st.session_state.get("chat_messages", [])
    step = st.session_state.get("current_step", 0)

    if st.session_state.get("pending_error"):
        err = st.session_state.pending_error
        return err, f"err_{step}_{_speech_key(err, lang)}"

    if messages:
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                text = msg["content"]
                return text, f"q_{step}_{_speech_key(text, lang)}"

    question = get_current_question(lang)
    return question, f"q_{step}_{_speech_key(question, lang)}"
