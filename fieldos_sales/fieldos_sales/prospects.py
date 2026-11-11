"""Import prospects from the target-firm spreadsheet and normalise phone numbers.

Expected sheet: "Firms" with the header row used by
project files sales/hyderabad-target-firms.xlsx (#, Firm, Segment, Size,
Priority, Suggested plan, Website, Public phone, Public email, Contact page,
Check status, Source, Owner notes, ...). Column names are matched loosely so
an edited copy still imports.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .store import Store

_COLUMNS = {
    "id": ("#", "id", "no"),
    "firm": ("firm", "company", "name"),
    "segment": ("segment",),
    "size": ("size",),
    "priority": ("priority",),
    "suggested_plan": ("suggested plan", "plan"),
    "website": ("website",),
    "phone": ("public phone", "phone", "mobile"),
    "emails": ("public email", "email"),
    "contact_page": ("contact page",),
    "source": ("source",),
    "owner_notes": ("owner notes", "notes"),
    "contact_name": ("contact name", "contact person"),
}


def normalise_indian_phone(raw: str) -> str | None:
    """Return +91XXXXXXXXXX for an Indian mobile or landline number, else None.

    Mobiles start 6-9. Landlines with an STD code (e.g. 040 for Hyderabad) are
    kept too, because calls may go to an office line; WhatsApp needs a mobile.
    """
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0091"):
        digits = digits[4:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10 or digits[0] == "0":
        return None
    return "+91" + digits


def is_indian_mobile(phone: str) -> bool:
    return bool(re.fullmatch(r"\+91[6-9]\d{9}", phone or ""))


def split_phones(cell: Any) -> list[str]:
    if not cell:
        return []
    out: list[str] = []
    for part in re.split(r"[,;/\n]| or ", str(cell)):
        p = normalise_indian_phone(part)
        if p and p not in out:
            out.append(p)
    return out


def _match_header(header: list[Any]) -> dict[str, int]:
    names = [str(h or "").strip().lower() for h in header]
    found: dict[str, int] = {}
    for key, options in _COLUMNS.items():
        for i, name in enumerate(names):
            if any(name == o or name.startswith(o) for o in options):
                found.setdefault(key, i)
                break
    return found


def import_xlsx(store: Store, path: Path, sheet: str = "Firms") -> int:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[sheet] if sheet in wb.sheetnames else wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = list(next(rows, []))
    cols = _match_header(header)
    if "firm" not in cols:
        raise ValueError(f"No 'Firm' column in sheet {ws.title!r}")

    def cell(row: tuple, key: str) -> Any:
        i = cols.get(key)
        return row[i] if i is not None and i < len(row) else None

    count = 0
    for n, row in enumerate(rows, start=1):
        firm = cell(row, "firm")
        if not firm:
            continue
        raw_id = cell(row, "id")
        try:
            pid = int(raw_id) if raw_id is not None else n
        except (TypeError, ValueError):
            pid = n
        store.upsert_prospect({
            "id": pid,
            "firm": str(firm).strip(),
            "segment": cell(row, "segment"),
            "size": cell(row, "size"),
            "priority": cell(row, "priority"),
            "suggested_plan": cell(row, "suggested_plan"),
            "website": (str(cell(row, "website")).strip() if cell(row, "website") else None),
            "phones": split_phones(cell(row, "phone")),
            "emails": cell(row, "emails"),
            "contact_page": cell(row, "contact_page"),
            "source": cell(row, "source"),
            "owner_notes": cell(row, "owner_notes"),
            "contact_name": cell(row, "contact_name"),
        })
        count += 1
    return count
