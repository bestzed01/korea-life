"""The Life Manager reminder engine.

Pure logic layer on top of the database module. Responsible for:
- computing the *display* status of an active reminder (upcoming / due soon /
  overdue) from its due date and advance-reminder offsets;
- marking items paid/completed and generating the next occurrence of a
  recurring reminder;
- snoozing;
- the reminder-check routine that runs on app open/refresh;
- feeding the notification center and the dashboard buckets.

Categories reflect the kinds of personal deadlines the app targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from . import database

# Display statuses (derived) vs stored statuses (completed/dismissed/upcoming)
STATUS_TODAY = "today"
STATUS_DUE_SOON = "due_soon"
STATUS_UPCOMING = "upcoming"
STATUS_OVERDUE = "overdue"
STATUS_COMPLETED = "completed"
STATUS_DISMISSED = "dismissed"

RECURRENCES = ["none", "weekly", "monthly", "yearly", "custom"]

CATEGORIES = [
    "health_insurance",
    "residence_card",
    "passport",
    "visa",
    "rent",
    "utilities",
    "tuition",
    "employment_contract",
    "subscription",
    "appointment",
    "tax",
    "task",
    "other",
]

CATEGORY_LABELS = {
    "health_insurance": "Health insurance",
    "residence_card": "Residence card",
    "passport": "Passport",
    "visa": "Visa / stay",
    "rent": "Rent",
    "utilities": "Utilities",
    "tuition": "Tuition",
    "employment_contract": "Employment contract",
    "subscription": "Subscription",
    "appointment": "Appointment",
    "tax": "Tax",
    "task": "Task",
    "other": "Other",
}

CATEGORY_ICONS = {
    "health_insurance": "🏥",
    "residence_card": "🪪",
    "passport": "📘",
    "visa": "🛂",
    "rent": "🏠",
    "utilities": "💡",
    "tuition": "🎓",
    "employment_contract": "📄",
    "subscription": "🔁",
    "appointment": "📅",
    "tax": "🧾",
    "task": "✅",
    "other": "📌",
}

# Default advance-reminder offsets suggested per category (days before due date).
DEFAULT_OFFSETS = {
    "residence_card": [60, 30, 7],
    "passport": [90, 60, 30],
    "visa": [60, 30, 7],
    "health_insurance": [7, 1],
    "rent": [5, 1],
    "utilities": [3, 1],
    "tuition": [14, 3],
    "employment_contract": [30, 7],
    "tax": [14, 3],
    "appointment": [3, 1],
    "subscription": [3, 1],
    "task": [3],
    "other": [3],
}


def _today() -> date:
    return date.today()


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category, category.replace("_", " ").title())


def category_icon(category: str) -> str:
    return CATEGORY_ICONS.get(category, "📌")


def default_offsets_for(category: str) -> List[int]:
    return list(DEFAULT_OFFSETS.get(category, [3]))


def days_until(due_date: str, ref: Optional[date] = None) -> Optional[int]:
    d = _parse_date(due_date)
    if not d:
        return None
    ref = ref or _today()
    return (d - ref).days


def compute_display_status(reminder: Dict[str, Any], ref: Optional[date] = None) -> str:
    """Return the status to show for a reminder.

    Stored completed/dismissed states win. Snoozed items are treated as
    upcoming until the snooze date passes. Otherwise the status is derived from
    the due date and the item's nearest advance-reminder offset.
    """
    ref = ref or _today()
    stored = (reminder.get("status") or "").lower()
    if stored in (STATUS_COMPLETED, STATUS_DISMISSED):
        return stored

    snoozed_until = _parse_date(reminder.get("snoozed_until"))
    if snoozed_until and snoozed_until > ref:
        return STATUS_UPCOMING

    due = _parse_date(reminder.get("due_date"))
    if not due:
        return STATUS_UPCOMING

    delta = (due - ref).days
    if delta < 0:
        return STATUS_OVERDUE
    if delta == 0:
        return STATUS_TODAY

    offsets = reminder.get("reminder_offsets") or []
    threshold = max(offsets) if offsets else 7
    if delta <= threshold:
        return STATUS_DUE_SOON
    return STATUS_UPCOMING


def active_offset_triggers(reminder: Dict[str, Any], ref: Optional[date] = None) -> List[int]:
    """Which advance-reminder offsets have been reached (for notifications)."""
    ref = ref or _today()
    delta = days_until(reminder.get("due_date", ""), ref)
    if delta is None or delta < 0:
        return []
    return sorted([o for o in (reminder.get("reminder_offsets") or []) if 0 <= delta <= o])


# ---------------------------------------------------------------------------
# Recurrence
# ---------------------------------------------------------------------------
def _add_months(d: date, months: int) -> date:
    """Add whole months to a date, clamping the day to the month's length."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    # clamp day
    if month == 2:
        last = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    elif month in (4, 6, 9, 11):
        last = 30
    else:
        last = 31
    return date(year, month, min(d.day, last))


def next_due_date(due_date: str, recurrence: str, interval: Optional[int] = None) -> Optional[str]:
    """Compute the next due date for a recurring reminder, or None if one-time."""
    d = _parse_date(due_date)
    if not d or recurrence == "none" or not recurrence:
        return None
    if recurrence == "weekly":
        nd = d + timedelta(days=7)
    elif recurrence == "monthly":
        nd = _add_months(d, 1)
    elif recurrence == "yearly":
        nd = _add_months(d, 12)
    elif recurrence == "custom":
        step = int(interval or 0)
        if step <= 0:
            return None
        nd = d + timedelta(days=step)
    else:
        return None
    return nd.isoformat()


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------
def complete_reminder(reminder_id: int) -> Optional[int]:
    """Mark a reminder completed/paid. If it recurs, create the next occurrence
    and return the new reminder's id; otherwise return None."""
    reminder = database.get_reminder(reminder_id)
    if not reminder:
        return None
    database.update_reminder(
        reminder_id,
        status=STATUS_COMPLETED,
        completed_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    nd = next_due_date(
        reminder["due_date"], reminder.get("recurrence", "none"), reminder.get("recurrence_interval")
    )
    if not nd:
        return None
    new_id = database.add_reminder(
        title=reminder["title"],
        category=reminder["category"],
        due_date=nd,
        amount=reminder.get("amount"),
        currency=reminder.get("currency", "KRW"),
        recurrence=reminder.get("recurrence", "none"),
        recurrence_interval=reminder.get("recurrence_interval"),
        reminder_offsets=reminder.get("reminder_offsets") or [],
        notes=reminder.get("notes", "") or "",
        source_ref=reminder.get("source_ref", "") or "",
        source_ids=reminder.get("source_ids") or [],
        created_from=reminder.get("created_from", "manual"),
        is_statutory=reminder.get("is_statutory", False),
    )
    return new_id


def snooze_reminder(reminder_id: int, days: int = 3) -> None:
    until = (_today() + timedelta(days=max(1, days))).isoformat()
    database.update_reminder(reminder_id, snoozed_until=until, status="upcoming")


def dismiss_reminder(reminder_id: int) -> None:
    database.update_reminder(reminder_id, status=STATUS_DISMISSED)


def reopen_reminder(reminder_id: int) -> None:
    database.update_reminder(reminder_id, status="upcoming", completed_at=None, snoozed_until=None)


# ---------------------------------------------------------------------------
# Views: dashboard buckets + notification center + reminder check
# ---------------------------------------------------------------------------
@dataclass
class DashboardBuckets:
    today: List[Dict[str, Any]]
    upcoming: List[Dict[str, Any]]
    overdue: List[Dict[str, Any]]
    completed: List[Dict[str, Any]]
    due_soon: List[Dict[str, Any]]


def build_buckets(ref: Optional[date] = None) -> DashboardBuckets:
    ref = ref or _today()
    reminders = database.list_reminders(include_completed=True)
    today, upcoming, overdue, completed, due_soon = [], [], [], [], []
    for r in reminders:
        r["_status"] = compute_display_status(r, ref)
        r["_days_until"] = days_until(r.get("due_date", ""), ref)
        s = r["_status"]
        if s == STATUS_COMPLETED:
            completed.append(r)
        elif s == STATUS_DISMISSED:
            continue
        elif s == STATUS_OVERDUE:
            overdue.append(r)
        elif s == STATUS_TODAY:
            today.append(r)
        elif s == STATUS_DUE_SOON:
            due_soon.append(r)
            upcoming.append(r)
        else:
            upcoming.append(r)
    return DashboardBuckets(today, upcoming, overdue, completed, due_soon)


def notification_center(ref: Optional[date] = None) -> List[Dict[str, Any]]:
    """Return items that should surface as notifications: overdue, due today,
    and those whose advance-reminder offset has been reached. Highest urgency
    first."""
    ref = ref or _today()
    buckets = build_buckets(ref)
    notes: List[Dict[str, Any]] = []
    for r in buckets.overdue:
        notes.append({**r, "_urgency": 0, "_reason": "Overdue"})
    for r in buckets.today:
        notes.append({**r, "_urgency": 1, "_reason": "Due today"})
    for r in buckets.due_soon:
        triggers = active_offset_triggers(r, ref)
        reason = f"Due in {r.get('_days_until')} day(s)"
        if triggers:
            reason = f"{min(triggers)}-day reminder • due in {r.get('_days_until')} day(s)"
        notes.append({**r, "_urgency": 2, "_reason": reason})
    notes.sort(key=lambda x: (x["_urgency"], x.get("_days_until") if x.get("_days_until") is not None else 999))
    return notes


def run_reminder_check(ref: Optional[date] = None) -> Dict[str, int]:
    """Lightweight check meant to run on every app open / refresh.

    It recomputes display statuses and returns a small summary used for the
    in-app notification badge. It does NOT send external notifications — that
    would require a continuously running scheduler (see README).
    """
    ref = ref or _today()
    buckets = build_buckets(ref)
    return {
        "overdue": len(buckets.overdue),
        "today": len(buckets.today),
        "due_soon": len(buckets.due_soon),
        "upcoming": len(buckets.upcoming),
        "completed": len(buckets.completed),
        "notifications": len(notification_center(ref)),
    }
