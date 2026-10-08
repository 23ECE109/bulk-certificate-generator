"""
PDF certificate generator using ReportLab.

A single predefined A4-landscape template is used for all certificates.
The template draws:
  - A decorative double border
  - The organisation logo / title area
  - The recipient's name (large, centred)
  - The event name and issuing authority
  - The issue date

All rendering is done synchronously so it can be called safely from either
the main thread or a background thread.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# A4 landscape dimensions in points
PAGE_W, PAGE_H = landscape(A4)


def generate_certificate(
    *,
    output_path: str,
    recipient_name: str,
    event_name: str,
    issued_by: str,
    issue_date: str,
) -> None:
    """
    Render a single certificate PDF to *output_path*.

    Parameters
    ----------
    output_path:     Absolute path where the PDF should be written.
    recipient_name:  Full name of the certificate recipient.
    event_name:      Name of the event / course.
    issued_by:       Issuing organisation or person.
    issue_date:      Date string to print (e.g. "2024-11-15").

    Raises
    ------
    Any exception from ReportLab propagates to the caller so the worker can
    mark the individual certificate as failed without crashing the whole job.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(output_path, pagesize=landscape(A4))

    _draw_background(c)
    _draw_outer_border(c)
    _draw_inner_border(c)
    _draw_header(c)
    _draw_body(c, recipient_name=recipient_name, event_name=event_name)
    _draw_footer(c, issued_by=issued_by, issue_date=issue_date)

    c.save()


# ---------------------------------------------------------------------------
# Private drawing helpers
# ---------------------------------------------------------------------------


def _draw_background(c: canvas.Canvas) -> None:
    """Soft ivory background."""
    c.setFillColor(colors.HexColor("#FDFAF3"))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def _draw_outer_border(c: canvas.Canvas) -> None:
    margin = 10 * mm
    c.setStrokeColor(colors.HexColor("#B8860B"))  # dark goldenrod
    c.setLineWidth(4)
    c.rect(margin, margin, PAGE_W - 2 * margin, PAGE_H - 2 * margin, fill=0, stroke=1)


def _draw_inner_border(c: canvas.Canvas) -> None:
    margin = 14 * mm
    c.setStrokeColor(colors.HexColor("#DAA520"))  # goldenrod
    c.setLineWidth(1.5)
    c.rect(margin, margin, PAGE_W - 2 * margin, PAGE_H - 2 * margin, fill=0, stroke=1)


def _draw_header(c: canvas.Canvas) -> None:
    # Decorative top line
    c.setStrokeColor(colors.HexColor("#B8860B"))
    c.setLineWidth(1)
    c.line(40 * mm, PAGE_H - 30 * mm, PAGE_W - 40 * mm, PAGE_H - 30 * mm)

    # "CERTIFICATE OF COMPLETION" title
    c.setFont("Times-Bold", 28)
    c.setFillColor(colors.HexColor("#4A3728"))
    c.drawCentredString(PAGE_W / 2, PAGE_H - 50 * mm, "CERTIFICATE OF COMPLETION")

    # Subtitle rule
    c.setStrokeColor(colors.HexColor("#B8860B"))
    c.setLineWidth(0.75)
    c.line(60 * mm, PAGE_H - 57 * mm, PAGE_W - 60 * mm, PAGE_H - 57 * mm)


def _draw_body(c: canvas.Canvas, *, recipient_name: str, event_name: str) -> None:
    mid_y = PAGE_H / 2

    # "This is to certify that"
    c.setFont("Times-Italic", 16)
    c.setFillColor(colors.HexColor("#5C4033"))
    c.drawCentredString(PAGE_W / 2, mid_y + 28 * mm, "This is to certify that")

    # Recipient name — large, prominent
    c.setFont("Times-BoldItalic", 38)
    c.setFillColor(colors.HexColor("#2C1810"))
    c.drawCentredString(PAGE_W / 2, mid_y + 8 * mm, recipient_name)

    # Underline beneath the name
    name_width = c.stringWidth(recipient_name, "Times-BoldItalic", 38)
    x_start = PAGE_W / 2 - name_width / 2
    x_end = PAGE_W / 2 + name_width / 2
    c.setStrokeColor(colors.HexColor("#B8860B"))
    c.setLineWidth(0.75)
    c.line(x_start, mid_y + 5 * mm, x_end, mid_y + 5 * mm)

    # "has successfully completed"
    c.setFont("Times-Italic", 16)
    c.setFillColor(colors.HexColor("#5C4033"))
    c.drawCentredString(PAGE_W / 2, mid_y - 7 * mm, "has successfully completed")

    # Event name
    c.setFont("Times-Bold", 20)
    c.setFillColor(colors.HexColor("#2C1810"))
    c.drawCentredString(PAGE_W / 2, mid_y - 22 * mm, event_name)


def _draw_footer(c: canvas.Canvas, *, issued_by: str, issue_date: str) -> None:
    footer_y = 28 * mm

    # Horizontal divider
    c.setStrokeColor(colors.HexColor("#B8860B"))
    c.setLineWidth(0.75)
    c.line(40 * mm, footer_y + 14 * mm, PAGE_W - 40 * mm, footer_y + 14 * mm)

    # Left column: issuer
    left_x = PAGE_W * 0.25
    c.setFont("Times-Bold", 12)
    c.setFillColor(colors.HexColor("#4A3728"))
    c.drawCentredString(left_x, footer_y + 7 * mm, issued_by)

    c.setFont("Times-Roman", 10)
    c.setFillColor(colors.HexColor("#7A6858"))
    c.drawCentredString(left_x, footer_y + 1 * mm, "Issued by")

    # Right column: date
    right_x = PAGE_W * 0.75
    c.setFont("Times-Bold", 12)
    c.setFillColor(colors.HexColor("#4A3728"))
    c.drawCentredString(right_x, footer_y + 7 * mm, issue_date)

    c.setFont("Times-Roman", 10)
    c.setFillColor(colors.HexColor("#7A6858"))
    c.drawCentredString(right_x, footer_y + 1 * mm, "Date")
