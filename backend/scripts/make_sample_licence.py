"""Generate a synthetic CDSCO Form 25 licence PDF for demos and testing.

Synthetic on purpose: a real manufacturer's licence is regulated data and
must not sit in a git repository. The layout mirrors a genuine Form 25
closely enough to exercise OCR realistically — headed fields, a licence
number in the standard MFG/25/<year>/<state>/<serial> format, and dates in
Indian DD/MM/YYYY convention.

Usage:
    python -m scripts.make_sample_licence [output.pdf]
"""
from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "docs" / "demo" / "sample_cdsco_licence.pdf"

LICENCE_NUMBER = "MFG/25/2024/KA/00847"
VENDOR_NAME = "Meridian Life Sciences Private Limited"


def build(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=A4)
    width, height = A4

    y = height - 30 * mm
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(width / 2, y, "FORM 25")

    y -= 8 * mm
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(width / 2, y, "LICENCE TO MANUFACTURE FOR SALE OR FOR DISTRIBUTION OF DRUGS")
    y -= 5 * mm
    c.setFont("Helvetica", 9)
    c.drawCentredString(width / 2, y, "(Other than those specified in Schedules C, C(1) and X)")

    y -= 6 * mm
    c.line(25 * mm, y, width - 25 * mm, y)

    rows = [
        ("Licence Number", LICENCE_NUMBER),
        ("Issued to", VENDOR_NAME),
        ("Premises", "Plot 14, Industrial Area Phase II, Peenya,"),
        ("", "Bengaluru 560058, Karnataka"),
        ("Issuing Authority", "Drugs Control Department, Government of Karnataka"),
        ("Date of Issue", "14/03/2024"),
        ("Valid Until", "13/03/2029"),
        ("Competent Technical Staff", "Dr. S. Ramachandran, M.Pharm"),
        ("GSTIN", "29AABCM1234K1Z5"),
    ]

    y -= 12 * mm
    for label, value in rows:
        if label:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(28 * mm, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(85 * mm, y, value)
        y -= 8 * mm

    y -= 4 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(28 * mm, y, "Categories of drugs authorised to be manufactured:")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    for item in ("1. Tablets (uncoated, film coated)",
                 "2. Capsules (hard gelatin)",
                 "3. Oral Liquids"):
        c.drawString(34 * mm, y, item)
        y -= 6 * mm

    y -= 6 * mm
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(
        28 * mm, y,
        "This licence is subject to the conditions prescribed under the Drugs and Cosmetics Act, 1940.",
    )
    y -= 4 * mm
    c.drawString(
        28 * mm, y,
        "SYNTHETIC SAMPLE - generated for software testing. Not a genuine licence.",
    )

    c.setFont("Helvetica", 10)
    c.drawString(width - 75 * mm, 35 * mm, "Licensing Authority")
    c.line(width - 76 * mm, 40 * mm, width - 28 * mm, 40 * mm)

    c.showPage()
    c.save()
    return path


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    built = build(out)
    print(f"[ok] wrote {built} ({built.stat().st_size:,} bytes)")
