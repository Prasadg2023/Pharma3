"""Email notification service using Gmail SMTP."""

import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

from config import SMTP_EMAIL, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_RECEIVER
from translations import t

logger = logging.getLogger(__name__)


def send_adr_report_email(
    report_id: int,
    reporter_name: str,
    pdf_path: Path,
    lang: str = "en",
) -> bool:
    """
    Send email notification with ADR PDF attachment.
    Returns True on success, False on failure.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD or not SMTP_RECEIVER:
        logger.warning("SMTP credentials not configured. Skipping email notification.")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = SMTP_EMAIL
        msg["To"] = SMTP_RECEIVER
        msg["Subject"] = t("email_subject", "en")

        body = f"""
A new Adverse Drug Reaction (ADR) report has been submitted through the PvPI ADR Reporting Chatbot.

Report ID: {report_id}
Reporter: {reporter_name}
Language: {lang}

Please find the attached PDF report for details.

---
This is an automated message from PvPI ADR Reporting Chatbot.
Pharmacovigilance Programme of India (PvPI)
        """.strip()

        msg.attach(MIMEText(body, "plain"))

        if pdf_path.exists():
            with open(pdf_path, "rb") as f:
                attachment = MIMEApplication(f.read(), _subtype="pdf")
                attachment.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=pdf_path.name,
                )
                msg.attach(attachment)

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, SMTP_RECEIVER, msg.as_string())

        logger.info("Email sent successfully for report ID: %s", report_id)
        return True

    except Exception as e:
        logger.error("Failed to send email for report %s: %s", report_id, e)
        return False


def is_email_configured() -> bool:
    """Check if SMTP is properly configured."""
    return bool(SMTP_EMAIL and SMTP_PASSWORD and SMTP_RECEIVER)
