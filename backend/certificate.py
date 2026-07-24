"""
certificate.py
Generates a polished, landscape "certificate of completion" PDF using reportlab.
"""

import os
from datetime import datetime
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

CERT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "certificates")

INK = HexColor("#0B0F0E")
ACCENT = HexColor("#2B7A6F")
ACCENT_LIGHT = HexColor("#5EEAD4")
MUTED = HexColor("#5B6B67")
GOLD = HexColor("#C9A24B")


def generate_certificate_pdf(certificate_id: str, user_name: str, topic: str,
                              score_percentage: float, issued_date: str = None) -> str:
    os.makedirs(CERT_DIR, exist_ok=True)
    filename = f"certificate_{certificate_id}.pdf"
    path = os.path.join(CERT_DIR, filename)

    issued_date = issued_date or datetime.utcnow().strftime("%B %d, %Y")
    page_size = landscape(A4)
    width, height = page_size

    c = canvas.Canvas(path, pagesize=page_size)

    # Background
    c.setFillColor(HexColor("#FBFAF6"))
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Outer border
    margin = 14 * mm
    c.setStrokeColor(ACCENT)
    c.setLineWidth(2.2)
    c.rect(margin, margin, width - 2 * margin, height - 2 * margin, fill=0, stroke=1)

    # Inner hairline border
    inner = margin + 5 * mm
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.8)
    c.rect(inner, inner, width - 2 * inner, height - 2 * inner, fill=0, stroke=1)

    center_x = width / 2

    # Brand mark
    c.setFillColor(ACCENT_LIGHT)
    c.circle(center_x, height - 34 * mm, 3.2 * mm, fill=1, stroke=0)
    c.setFillColor(INK)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(center_x, height - 40 * mm, "LEARNLAB")
    c.setFont("Helvetica", 8.5)
    c.setFillColor(MUTED)
    c.drawCentredString(center_x, height - 44.5 * mm, "AI-POWERED LEARNING PLATFORM")

    # Title
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(INK)
    c.drawCentredString(center_x, height - 62 * mm, "Certificate of Completion")

    c.setFont("Helvetica", 11.5)
    c.setFillColor(MUTED)
    c.drawCentredString(center_x, height - 71 * mm, "This certifies that")

    # Name
    c.setFont("Helvetica-Bold", 26)
    c.setFillColor(ACCENT)
    c.drawCentredString(center_x, height - 84 * mm, user_name)

    # underline flourish
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(center_x - 55 * mm, height - 88 * mm, center_x + 55 * mm, height - 88 * mm)

    c.setFont("Helvetica", 11.5)
    c.setFillColor(MUTED)
    c.drawCentredString(center_x, height - 98 * mm, "has successfully completed the learning module and assessment on")

    c.setFont("Helvetica-Bold", 19)
    c.setFillColor(INK)
    c.drawCentredString(center_x, height - 109 * mm, topic)

    c.setFont("Helvetica", 11)
    c.setFillColor(MUTED)
    c.drawCentredString(
        center_x, height - 119 * mm,
        f"achieving a final assessment score of {score_percentage:.0f}%"
    )

    # Footer: date / signature / certificate id
    foot_y = margin + 18 * mm
    c.setStrokeColor(MUTED)
    c.setLineWidth(0.6)

    c.line(margin + 22 * mm, foot_y + 9 * mm, margin + 70 * mm, foot_y + 9 * mm)
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawCentredString(margin + 46 * mm, foot_y + 4 * mm, "Date Issued")
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK)
    c.drawCentredString(margin + 46 * mm, foot_y + 10.5 * mm, issued_date)

    c.line(width - margin - 70 * mm, foot_y + 9 * mm, width - margin - 22 * mm, foot_y + 9 * mm)
    c.setFont("Helvetica", 9)
    c.setFillColor(MUTED)
    c.drawCentredString(width - margin - 46 * mm, foot_y + 4 * mm, "LearnLab Academic Team")
    c.setFont("Helvetica-Oblique", 12)
    c.setFillColor(ACCENT)
    c.drawCentredString(width - margin - 46 * mm, foot_y + 10.5 * mm, "LearnLab")

    c.setFont("Helvetica", 7.5)
    c.setFillColor(MUTED)
    c.drawCentredString(center_x, margin + 6 * mm, f"Certificate ID: {certificate_id}")

    c.showPage()
    c.save()
    return path
