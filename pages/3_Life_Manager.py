"""Life Manager — the core reminder module.

Create reminders manually or from a pasted notice (with confirmation), manage
recurrence and advance-reminder offsets, and work the Today / Upcoming /
Overdue / Completed dashboard with mark-paid, snooze, edit and delete.
"""
from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from korealife import database, extract, reminders, ui
from korealife.i18n import t

st.set_page_config(page_title="Life Manager · KOREA-LIFE", page_icon="🗂️", layout="wide")
ui.inject_css()
ui.ensure_db()
profile = ui.sidebar_status()

if not profile:
    st.warning("Please complete onboarding on the Home page first.")
    st.stop()

lang = profile.get("language", "en")
ui.page_header("Life Manager", t("life_manager", lang), "One-time & recurring reminders for the deadlines that matter.")

tab_dash, tab_new, tab_notice, tab_manage = st.tabs(
    ["📊 Dashboard", "➕ New reminder", "📄 From a notice", "✏️ Manage"]
)

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
with tab_dash:
    summary = reminders.run_reminder_check()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("🔴 " + t("overdue", lang), summary["overdue"])
    m2.metric("🟠 " + t("today", lang), summary["today"])
    m3.metric("🔵 Due soon", summary["due_soon"])
    m4.metric("🟢 " + t("completed", lang), summary["completed"])

    buckets = reminders.build_buckets()

    st.subheader(f"🔴 {t('overdue', lang)} ({len(buckets.overdue)})")
    for r in buckets.overdue:
        ui.reminder_card(r, key_prefix="lm_over")
    if not buckets.overdue:
        st.caption("Nothing overdue.")

    st.subheader(f"🟠 {t('today', lang)} ({len(buckets.today)})")
    for r in buckets.today:
        ui.reminder_card(r, key_prefix="lm_today")
    if not buckets.today:
        st.caption("Nothing due today.")

    st.subheader(f"🔵 {t('upcoming', lang)} ({len(buckets.upcoming)})")
    for r in buckets.upcoming:
        ui.reminder_card(r, key_prefix="lm_up")
    if not buckets.upcoming:
        st.caption("No upcoming reminders.")

    with st.expander(f"🟢 {t('completed', lang)} ({len(buckets.completed)})"):
        for r in buckets.completed:
            ui.reminder_card(r, key_prefix="lm_done")
        if not buckets.completed:
            st.caption("Nothing completed yet.")

# ---------------------------------------------------------------------------
# New reminder (manual)
# ---------------------------------------------------------------------------
with tab_new:
    st.caption(
        "Create any personal deadline. For health insurance, use your **actual** bill "
        "due date and set it to recur monthly. For documents, pick multiple advance reminders."
    )
    with st.form("new_reminder"):
        title = st.text_input("Title", placeholder="e.g. NHIS premium, Residence card expiry, Apartment rent")
        cat_col, due_col = st.columns(2)
        with cat_col:
            category = st.selectbox(
                "Category", reminders.CATEGORIES, format_func=reminders.category_label
            )
        with due_col:
            due = st.date_input("Due date", value=date.today() + timedelta(days=30))

        amt_col, cur_col = st.columns(2)
        with amt_col:
            amount = st.number_input("Amount (optional)", min_value=0.0, value=0.0, step=1000.0)
        with cur_col:
            currency = st.selectbox("Currency", ["KRW", "USD", "RUB", "UZS", "other"], index=0)

        rec_col, int_col = st.columns(2)
        with rec_col:
            recurrence = st.selectbox(
                "Recurrence", reminders.RECURRENCES,
                format_func=lambda r: {"none": "One-time", "weekly": "Weekly", "monthly": "Monthly",
                                        "yearly": "Yearly", "custom": "Custom (every N days)"}.get(r, r),
            )
        with int_col:
            interval = st.number_input("Custom interval (days)", min_value=0, value=0, step=1,
                                       help="Only used when recurrence is Custom.")

        st.markdown("**Advance reminders** — how many days before the due date to be reminded")
        default_off = reminders.default_offsets_for(category)
        offsets = st.multiselect(
            "Reminder offsets (days before)",
            options=[1, 3, 7, 14, 30, 60, 90],
            default=[o for o in default_off if o in [1, 3, 7, 14, 30, 60, 90]],
        )
        notes = st.text_area("Notes (optional)", placeholder="Any details you want to remember")
        source_ref = st.text_input("Source / document reference (optional)", placeholder="e.g. NHIS bill #, letter dated ...")

        is_statutory = st.checkbox(
            "This is a deadline I verified from an official source",
            value=False,
            help="Leave unchecked to keep it as a personal reminder. Only check this if an official "
                 "source confirmed the exact legal deadline.",
        )
        submitted = st.form_submit_button("Create reminder", type="primary")

    if submitted:
        if not title.strip():
            st.error("Please enter a title.")
        elif recurrence == "custom" and interval <= 0:
            st.error("Custom recurrence needs an interval greater than 0 days.")
        else:
            database.add_reminder(
                title=title,
                category=category,
                due_date=due.isoformat(),
                amount=amount if amount > 0 else None,
                currency=currency,
                recurrence=recurrence,
                recurrence_interval=int(interval) if recurrence == "custom" else None,
                reminder_offsets=sorted(offsets, reverse=True),
                notes=notes,
                source_ref=source_ref,
                created_from="manual",
                is_statutory=is_statutory,
            )
            st.success(f"Created '{title}'.")
            st.rerun()

# ---------------------------------------------------------------------------
# From a notice (AI/regex extraction with confirmation)
# ---------------------------------------------------------------------------
with tab_notice:
    st.caption(
        "Paste the text of a bill or official notice (or upload a .txt). The app will "
        "**suggest** dates and amounts it finds. Nothing is saved until you review and confirm. "
        "The app never infers statutory deadlines or universal due dates."
    )
    uploaded = st.file_uploader("Upload a .txt notice (optional)", type=["txt"])
    pasted = st.text_area("...or paste the notice text here", height=140,
                          value=st.session_state.get("notice_text", ""))

    text = ""
    if uploaded is not None:
        try:
            text = uploaded.read().decode("utf-8", errors="ignore")
        except Exception:
            st.error("Could not read the uploaded file as text.")
    if pasted.strip():
        text = pasted

    if st.button("🔍 Extract candidates"):
        if not text.strip():
            st.error("Please paste or upload some notice text first.")
        else:
            st.session_state["notice_text"] = text
            st.session_state["notice_candidates"] = extract.extract_candidates(text)

    cand = st.session_state.get("notice_candidates")
    if cand:
        st.info(cand["note"])
        st.markdown(f"**Dates found:** {', '.join(cand['dates']) if cand['dates'] else 'none'}")
        st.markdown(
            f"**Amounts found:** "
            + (", ".join(f"{a:,.0f}" for a in cand["amounts"]) if cand["amounts"] else "none")
        )
        st.divider()
        st.markdown("**Confirm and save as a personal reminder**")
        with st.form("confirm_notice"):
            title = st.text_input("Title", placeholder="e.g. NHIS premium (from notice)")
            category = st.selectbox("Category", reminders.CATEGORIES, format_func=reminders.category_label)
            default_due = cand.get("suggested_due_date") or date.today().isoformat()
            try:
                due_val = date.fromisoformat(default_due)
            except ValueError:
                due_val = date.today()
            due = st.date_input("Due date (confirm)", value=due_val)
            amount = st.number_input(
                "Amount (confirm)", min_value=0.0,
                value=float(cand.get("suggested_amount") or 0.0), step=1000.0,
            )
            recurrence = st.selectbox(
                "Recurrence", reminders.RECURRENCES,
                format_func=lambda r: {"none": "One-time", "weekly": "Weekly", "monthly": "Monthly",
                                        "yearly": "Yearly", "custom": "Custom"}.get(r, r),
            )
            offsets = st.multiselect("Advance reminders (days before)", [1, 3, 7, 14, 30, 60, 90], default=[7, 1])
            confirm = st.form_submit_button("✅ Confirm & save", type="primary")
        if confirm:
            if not title.strip():
                st.error("Please enter a title.")
            else:
                database.add_reminder(
                    title=title,
                    category=category,
                    due_date=due.isoformat(),
                    amount=amount if amount > 0 else None,
                    recurrence=recurrence,
                    reminder_offsets=sorted(offsets, reverse=True),
                    notes="Created from a notice (user-confirmed).",
                    source_ref="notice/bill text",
                    created_from="ai",
                    is_statutory=False,
                )
                st.success("Saved as a personal reminder. Verify any official deadline with the issuer.")
                st.session_state.pop("notice_candidates", None)
                st.session_state.pop("notice_text", None)

# ---------------------------------------------------------------------------
# Manage (edit / delete)
# ---------------------------------------------------------------------------
with tab_manage:
    items = database.list_reminders(include_completed=True)
    if not items:
        st.caption("No reminders yet.")
    for r in items:
        with st.expander(f"{reminders.category_icon(r['category'])} {r['title']} — due {r['due_date']}"):
            with st.form(f"edit_{r['id']}"):
                title = st.text_input("Title", value=r["title"])
                c1, c2 = st.columns(2)
                with c1:
                    category = st.selectbox(
                        "Category", reminders.CATEGORIES,
                        index=reminders.CATEGORIES.index(r["category"]) if r["category"] in reminders.CATEGORIES else len(reminders.CATEGORIES) - 1,
                        format_func=reminders.category_label, key=f"ec_{r['id']}",
                    )
                with c2:
                    try:
                        due_val = date.fromisoformat(r["due_date"][:10])
                    except ValueError:
                        due_val = date.today()
                    due = st.date_input("Due date", value=due_val, key=f"ed_{r['id']}")
                notes = st.text_area("Notes", value=r.get("notes", "") or "", key=f"en_{r['id']}")
                is_statutory = st.checkbox(
                    "Verified official deadline", value=bool(r.get("is_statutory")), key=f"es_{r['id']}"
                )
                cc1, cc2 = st.columns(2)
                save = cc1.form_submit_button("💾 Save changes")
                delete = cc2.form_submit_button("🗑 Delete")
            if save:
                database.update_reminder(
                    r["id"], title=title, category=category, due_date=due.isoformat(),
                    notes=notes, is_statutory=is_statutory,
                )
                st.success("Updated.")
                st.rerun()
            if delete:
                database.delete_reminder(r["id"])
                st.rerun()

st.divider()
st.caption(
    "⚙️ **About notifications:** this prototype shows reminders in-app and refreshes them each "
    "time the app opens. It does **not** send email, SMS, or push notifications — those require a "
    "continuously running scheduler or notification service (see the README)."
)
