"""KOREA-LIFE — Home dashboard & onboarding (Streamlit entry point).

Run with:  streamlit run app.py
"""
from __future__ import annotations

import streamlit as st

from korealife import config, database, reminders, ui
from korealife.i18n import t

st.set_page_config(page_title="KOREA-LIFE", page_icon="🇰🇷", layout="wide")
ui.inject_css()
ui.ensure_db()

profile = ui.sidebar_status()

# ---------------------------------------------------------------------------
# Onboarding gate
# ---------------------------------------------------------------------------
if not profile:
    ui.page_header("KOREA-LIFE", "Life in Korea, organized",
                   "Your multilingual guide to official services, deadlines, and institutions in South Korea.")
    ui.utility_bar("Official information portal for foreign residents in the Republic of Korea.")
    col1, col2 = st.columns([2, 1])
    with col1:
        ui.onboarding_form()
    with col2:
        st.subheader("Try the demo")
        st.caption(
            "Load a **synthetic** demo profile and sample reminders so you can explore "
            "immediately. All demo data is clearly labeled and fictional."
        )
        if st.button("Load synthetic demo profile", type="primary"):
            ui.load_demo_profile()
            st.rerun()
        st.divider()
        st.markdown(ui.mode_badge(), unsafe_allow_html=True)
        if not config.ai_enabled():
            st.info(
                "No ANTHROPIC_API_KEY detected — the app runs in **offline demo mode** with "
                "deterministic answers grounded in the local official-source records."
            )
        st.caption("This platform has two sides: residents (here) and institutions (KOREA-LIFE Connect).")
    st.stop()

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
lang = profile.get("language", "en")
from datetime import date
ui.page_header("Dashboard", "Your deadlines & official guidance",
               f"{date.today().strftime('%A, %d %B %Y')} · {t('app_tagline', lang)}")
ui.utility_bar("Official information portal for foreign residents in the Republic of Korea.")

if profile.get("is_demo"):
    st.markdown(
        "<div class='kl-utility' style='border-left-color:#b45309'>🧪 "
        "<b>Synthetic demo profile.</b>&nbsp; All records shown are fictional sample data, not real documents.</div>",
        unsafe_allow_html=True,
    )

summary = reminders.run_reminder_check()
ui.stat_cards([
    {"label": "Overdue", "value": summary["overdue"], "foot": "No action required" if not summary["overdue"] else "Needs attention", "tone": "red"},
    {"label": "Due today", "value": summary["today"], "foot": "Nothing due today" if not summary["today"] else "Due today", "tone": "amber"},
    {"label": "Due soon", "value": summary["due_soon"], "foot": "Next 7 days", "tone": "blue"},
    {"label": "Completed", "value": summary["completed"], "foot": "Up to date", "tone": "green"},
])

ui.trust_band()

# Notification center
notes = reminders.notification_center()
with st.expander(f"🔔 Notification center ({len(notes)})", expanded=bool(notes)):
    if not notes:
        st.success("Nothing needs your attention right now.")
    else:
        st.caption(
            "In-app notifications only. External alerts (email/SMS/push) require a continuously "
            "running scheduler — see the README. This prototype does not send them."
        )
        for n in notes:
            icon = reminders.category_icon(n.get("category", "other"))
            st.markdown(f"- **{n['_reason']}** — {icon} {n['title']} (due {n['due_date']})")

st.write("")
buckets = reminders.build_buckets()
left, right = st.columns(2)
with left:
    st.markdown("##### 🔴 Needs attention")
    attention = buckets.overdue + buckets.today
    if attention:
        for r in attention:
            ui.record_card(r)
    else:
        ui.empty_state("No overdue or same-day deadlines", "Items move here as their due date approaches.")

with right:
    st.markdown("##### 🔵 Upcoming deadlines")
    if buckets.upcoming:
        for r in buckets.upcoming[:12]:
            ui.record_card(r)
    else:
        ui.empty_state("No upcoming reminders yet", "Add reminders in Life Manager or save action steps from the AI Copilot.")

if buckets.completed:
    with st.expander(f"🟢 Completed ({len(buckets.completed)})"):
        for r in buckets.completed[:8]:
            ui.record_card(r)

st.markdown(
    "<div class='kl-note'>Saved dates are <b>personal reminders</b>, not statutory deadlines, unless "
    "verified from an official source. KOREA-LIFE provides navigation and official references only — "
    "it is not legal, immigration, labor, healthcare, or financial advice.</div>",
    unsafe_allow_html=True,
)

with st.expander("⚙️ Edit profile / manage data"):
    ui.onboarding_form(prefill=profile)
    st.divider()
    cc1, cc2 = st.columns(2)
    with cc1:
        if st.button("Reset profile"):
            database.clear_profile()
            st.rerun()
    with cc2:
        if st.button("Delete ALL reminders"):
            database.delete_all_reminders()
            st.rerun()
