"""Extract candidate dates and amounts from a pasted notice/bill text.

Used by the Life Manager "create from a notice" flow. Extraction NEVER saves
anything on its own — it only proposes candidates that the user must review and
confirm. In fallback mode it uses regular expressions; with an API key it can
ask Claude to extract, but the regex result is always available as a safe
baseline.

Crucially, this never infers a statutory deadline or a universal payment date.
It only surfaces dates/amounts literally present in the text, for the user to
confirm as a *personal reminder*.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

# Date patterns commonly seen on Korean bills/notices rendered in English or digits.
_DATE_PATTERNS = [
    (re.compile(r"\b(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})\b"), "ymd"),            # 2026.03.15 / 2026-3-5
    (re.compile(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](20\d{2})\b"), "dmy_or_mdy"),      # 15/03/2026
    (re.compile(r"\b(20\d{2})년\s*(\d{1,2})월\s*(\d{1,2})일"), "ymd"),               # 2026년 3월 15일
    (re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(20\d{2})\b"), "dmonthy"),         # 15 March 2026
    (re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(20\d{2})\b"), "monthdy"),        # March 15, 2026
]

_MONTHS = {
    m.lower(): i
    for i, m in enumerate(
        ["January", "February", "March", "April", "May", "June", "July",
         "August", "September", "October", "November", "December"], start=1)
}
_MONTHS.update({m[:3].lower(): i for m, i in list(_MONTHS.items())})

# Amount patterns: ₩, KRW, won, or digit groups with commas.
_AMOUNT_PATTERNS = [
    re.compile(r"(?:₩|\bKRW\b|\bwon\b)\s*([0-9][0-9,]{2,})", re.IGNORECASE),
    re.compile(r"([0-9][0-9,]{3,})\s*(?:원|won|KRW)", re.IGNORECASE),
]


def _valid_date(y: int, m: int, d: int) -> Optional[str]:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def extract_dates(text: str) -> List[str]:
    found: List[str] = []
    for pattern, kind in _DATE_PATTERNS:
        for match in pattern.finditer(text or ""):
            g = match.groups()
            iso: Optional[str] = None
            if kind == "ymd":
                iso = _valid_date(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "dmy_or_mdy":
                # Ambiguous: prefer d/m/y, fall back to m/d/y.
                iso = _valid_date(int(g[2]), int(g[1]), int(g[0])) or _valid_date(int(g[2]), int(g[0]), int(g[1]))
            elif kind == "dmonthy":
                month = _MONTHS.get(g[1].lower())
                if month:
                    iso = _valid_date(int(g[2]), month, int(g[0]))
            elif kind == "monthdy":
                month = _MONTHS.get(g[0].lower())
                if month:
                    iso = _valid_date(int(g[2]), month, int(g[1]))
            if iso and iso not in found:
                found.append(iso)
    return sorted(found)


def extract_amounts(text: str) -> List[float]:
    found: List[float] = []
    for pattern in _AMOUNT_PATTERNS:
        for match in pattern.finditer(text or ""):
            raw = match.group(1).replace(",", "")
            try:
                value = float(raw)
            except ValueError:
                continue
            if value >= 100 and value not in found:  # ignore tiny noise
                found.append(value)
    return sorted(found, reverse=True)


def extract_candidates(text: str) -> Dict[str, Any]:
    """Return proposed dates and amounts for user confirmation. Pure, local, safe."""
    text = text or ""
    dates = extract_dates(text)
    amounts = extract_amounts(text)
    # Prefer a future-looking due date as the default suggestion.
    today = date.today()
    future = [d for d in dates if datetime.strptime(d, "%Y-%m-%d").date() >= today]
    suggested_due = (future[0] if future else (dates[0] if dates else ""))
    return {
        "dates": dates,
        "amounts": amounts,
        "suggested_due_date": suggested_due,
        "suggested_amount": amounts[0] if amounts else None,
        "note": "These candidates were read from the text you pasted. Review and confirm before saving. They become a PERSONAL reminder, not an official/statutory deadline.",
    }
