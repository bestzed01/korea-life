"""My Life Plan — the full list of saved tasks & reminders with completion
status, upcoming dates and countdowns. A planning-oriented view over the same
data the Life Manager and Home dashboard use."""
from __future__ import annotations

import streamlit as st

from korealife import database, reminders, ui
from korealife.i18n import t

st.set_page_config(page_title="My Life Plan · KOREA-LIFE", page_icon="🗺️", layout="wide")
ui.inject_css()
ui.ensure_db()
profile = ui.sidebar_status()

if not profile:
    st.warning("Please complete onboarding on the Home page first.")
    st.stop()

lang = profile.get("language", "en")
ui.page_header("My Life Plan", t("life_plan", lang), "Everything you're tracking, with countdowns and status.")

all_items = database.list_reminders(include_completed=True)
for r in all_items:
    r["_status"] = reminders.compute_display_status(r)
    r["_days_until"] = reminders.days_until(r.get("due_date", ""))

if not all_items:
    st.info("You have no saved tasks or reminders yet. Add them in Life Manager, or save action steps from the AI Copilot.")
    st.stop()

# Filters
c1, c2 = st.columns([1, 1])
with c1:
    cats = ["(all)"] + reminders.CATEGORIES
    cat_filter = st.selectbox("Filter by category", cats, format_func=lambda c: "All categories" if c == "(all)" else reminders.category_label(c))
with c2:
    show_completed = st.checkbox("Show completed", value=True)

filtered = []
for r in all_items:
    if cat_filter != "(all)" and r.get("category") != cat_filter:
        continue
    if not show_completed and r["_status"] == reminders.STATUS_COMPLETED:
        continue
    filtered.append(r)

# Summary metrics
active = [r for r in filtered if r["_status"] not in (reminders.STATUS_COMPLETED, reminders.STATUS_DISMISSED)]
m1, m2, m3 = st.columns(3)
m1.metric("Tracked items", len(filtered))
m2.metric("Active", len(active))
m3.metric("From AI plans", sum(1 for r in filtered if r.get("created_from") == "ai"))

st.divider()

# Order: overdue, today, due_soon, upcoming, completed
order = {
    reminders.STATUS_OVERDUE: 0,
    reminders.STATUS_TODAY: 1,
    reminders.STATUS_DUE_SOON: 2,
    reminders.STATUS_UPCOMING: 3,
    reminders.STATUS_COMPLETED: 4,
    reminders.STATUS_DISMISSED: 5,
}
filtered.sort(key=lambda r: (order.get(r["_status"], 9), r.get("due_date", "")))

for r in filtered:
    ui.reminder_card(r, key_prefix="plan")

st.divider()
st.caption(
    "All items are **personal reminders** unless marked as a verified official deadline. "
    "Countdowns are informational; confirm any legal deadline with the official source."
)
