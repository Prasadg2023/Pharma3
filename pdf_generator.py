"""PDF generation for ADR reports using FPDF2."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from fpdf import FPDF

from config import REPORTS_DIR
from translations import ADR_FIELDS, t


class ADRReportPDF(FPDF):
    """Custom PDF class for ADR reports."""

    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(0, 82, 147)
        self.cell(0, 10, self.doc_title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_font("Helvetica", "I", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, self.doc_subtitle, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_draw_color(0, 82, 147)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-20)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, self.doc_footer, align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, self.doc_confidential, align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="C")


def _section_header(pdf: ADRReportPDF, title: str) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(230, 240, 250)
    pdf.set_text_color(0, 82, 147)
    pdf.cell(0, 8, f"  {title}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_text_color(0, 0, 0)


def _field_row(pdf: ADRReportPDF, label: str, value: str) -> None:
    pdf.set_font("Helvetica", "B", 10)
    label_text = f"{label}:"
    pdf.cell(55, 7, label_text, new_x="RIGHT", new_y="TOP")
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(0, 7, value or "N/A", new_x="LMARGIN", new_y="NEXT")


def generate_adr_pdf(
    report_data: dict,
    report_id: int,
    reporter_name: str,
    lang: str = "en",
) -> Path:
    """
    Generate ADR report PDF and return file path.
    """
    pdf = ADRReportPDF()
    pdf.doc_title = t("pdf_title", lang)
    pdf.doc_subtitle = t("pdf_subtitle", lang)
    pdf.doc_footer = t("pdf_footer", lang)
    pdf.doc_confidential = t("pdf_confidential", lang)

    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # Report metadata
    pdf.set_font("Helvetica", "", 10)
    report_date = datetime.now().strftime("%d/%m/%Y %H:%M")
    _field_row(pdf, t("pdf_date", lang), report_date)
    _field_row(pdf, t("pdf_reporter", lang), reporter_name)
    _field_row(pdf, "Report ID", str(report_id))
    pdf.ln(4)

    fields = report_data.get("fields", report_data)

    patient_keys = ["patient_initial", "age", "gender", "weight"]
    reaction_keys = [
        "reaction_start", "reaction_stop", "reaction_description",
        "serious", "outcome",
    ]
    medicine_keys = [
        "medicine_name", "dose", "route", "frequency",
        "medicine_start", "medicine_stop", "indication", "action_taken",
    ]

    sections = [
        (t("pdf_section_patient", lang), patient_keys),
        (t("pdf_section_reaction", lang), reaction_keys),
        (t("pdf_section_medicine", lang), medicine_keys),
    ]

    label_map = {fk: lk for fk, _, lk in ADR_FIELDS}

    for section_title, keys in sections:
        _section_header(pdf, section_title)
        for key in keys:
            field = fields.get(key, {})
            if isinstance(field, dict):
                value = field.get("value_en", field.get("value_original", ""))
                original = field.get("value_original", "")
                if original and original != value:
                    value = f"{value} ({original})"
            else:
                value = str(field) if field else "N/A"

            label = t(label_map.get(key, key), lang)
            _field_row(pdf, label, value)
        pdf.ln(4)

    # Reporter section
    reporter_field = fields.get("reporter_name", {})
    if isinstance(reporter_field, dict):
        reporter_val = reporter_field.get("value_en", reporter_name)
    else:
        reporter_val = reporter_name

    _section_header(pdf, t("field_reporter_name", lang))
    _field_row(pdf, t("field_reporter_name", lang), reporter_val)

    filename = f"ADR_Report_{report_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = REPORTS_DIR / filename
    pdf.output(str(filepath))

    return filepath


def get_pdf_bytes(filepath: Path) -> bytes:
    """Read PDF file and return bytes for download."""
    with open(filepath, "rb") as f:
        return f.read()
