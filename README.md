# PvPI ADR Reporting Chatbot — College Project

A **voice-enabled** multilingual Streamlit webapp for reporting Adverse Drug Reactions (ADR), inspired by India's Pharmacovigilance Programme (PvPI).

> **Academic prototype only** — for college demonstration, not for official medical use.

## Voice Conversation Mode

The chatbot talks to you like a real conversation:

1. **Bot speaks the question aloud** (text-to-speech in English / Hindi / Marathi)
2. **You answer by voice** — tap the microphone and speak
3. Moves to the next question automatically

Example flow:
- 🔊 *"What is the patient's initial?"* (spoken aloud)
- 🎤 You say: *"A"*
- 🔊 *"What is the patient's age?"* (next question spoken)

## Quick Start

```powershell
cd pvpi-chatbot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open **http://localhost:8501** — allow **microphone** permission in the browser.

## Login

| Username      | Password    | Role        |
|---------------|-------------|-------------|
| `doctor1`     | `doctor123` | Doctor      |
| `pharmacist1` | `pharma123` | Pharmacist  |
| `admin`       | `admin123`  | Admin       |

## Features (for college viva / report)

| Feature | Description |
|---------|-------------|
| Voice Q&A | Bot asks via TTS, user answers via microphone |
| 3 Languages | English, Hindi, Marathi |
| 18-step ADR form | Patient, reaction, medicine details |
| SQLite database | No PostgreSQL install needed |
| Login & roles | Doctor, Pharmacist, Admin |
| PDF report | Download after submission |
| Admin dashboard | Charts, search, CSV export |

## Tips for demo

- Use **Chrome or Edge** for best voice support
- Select language in sidebar before starting
- Click **Repeat question** if you missed the audio
- Use **Type answer instead** if microphone fails in exam hall

## Project Structure

```
pvpi-chatbot/
├── app.py           # Main voice chatbot UI
├── voice_service.py # Text-to-speech + speech-to-text
├── chatbot.py       # 18-step ADR logic
├── data/            # SQLite database (auto-created)
└── pages/Admin.py   # Admin dashboard
```

## Tech Stack

Python 3.12 · Streamlit · SQLite · Web Speech API · deep-translator · FPDF2
