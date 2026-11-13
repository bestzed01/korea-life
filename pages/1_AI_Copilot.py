"""AI Copilot — ask questions, get source-grounded structured answers, and
turn action steps into tracked reminders."""
from __future__ import annotations

import json

import streamlit as st

from korealife import ai, config, connect, database, knowledge, reminders, ui
from korealife.config import DEMO_QUESTIONS_PATH
from korealife.i18n import t

st.set_page_config(page_title="AI Copilot · KOREA-LIFE", page_icon="💬", layout="wide")
ui.inject_css()
ui.ensure_db()
profile = ui.sidebar_status()

if not profile:
    st.warning("Please complete onboarding on the Home page first.")
    st.stop()

lang = profile.get("language", "en")
ui.page_header("AI Copilot", t("copilot", lang),
               "Answers grounded only in retrieved official sources and verified organization info — with safety checks.")

st.markdown(ui.mode_badge(), unsafe_allow_html=True)
st.caption(knowledge.disclaimer())

# Demo questions ------------------------------------------------------------
with st.expander("💡 Demo questions (synthetic examples)"):
    try:
        with open(DEMO_QUESTIONS_PATH, "r", encoding="utf-8") as fh:
            demo_qs = json.load(fh).get("questions", [])
    except Exception:
        demo_qs = []
    st.caption("These are example prompts, not personalized advice.")
    cols = st.columns(2)
    for i, q in enumerate(demo_qs):
        if cols[i % 2].button(q, key=f"demoq_{i}"):
            st.session_state["copilot_query"] = q

# Input ---------------------------------------------------------------------
query = st.text_area(
    "Your question",
    value=st.session_state.get("copilot_query", ""),
    placeholder=t("ask_placeholder", lang),
    height=90,
)
ask_clicked = st.button("Ask KOREA-LIFE", type="primary")

if ask_clicked and query.strip():
    with st.spinner("Retrieving official sources and composing an answer..."):
        result = ai.ask(query, profile=profile)
    st.session_state["last_result"] = result
    st.session_state["last_query"] = query

result = st.session_state.get("last_result")
if result:
    query = st.session_state.get("last_query", "")
    st.divider()

    # Mode / verification banners
    if result.get("mode") == "fallback":
        st.info(
            "🔵 **Offline demo answer (fallback mode).** "
            + result.get("_fallback_reason", "No ANTHROPIC_API_KEY configured.")
            + " This answer is deterministic and grounded in the retrieved official-source records."
        )
    if result.get("needs_official_verification"):
        st.error(
            "🚩 **High-stakes topic — official verification required.** This may involve "
            "immigration, legal, labor, healthcare, or financial matters. Confirm with the "
            "official contact below before acting. KOREA-LIFE does not provide legal advice "
            "and does not state visa rules, eligibility, or deadlines."
        )

    # Answer
    st.subheader("Answer")
    st.write(result.get("answer", ""))

    unc = result.get("uncertainty", "medium")
    unc_color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(unc, "🟡")
    st.caption(f"Confidence / uncertainty: {unc_color} {unc}")

    if result.get("applicability"):
        st.markdown("**How this applies to you**")
        st.write(result["applicability"])

    # Korean script
    if result.get("korean_script"):
        st.markdown("**🗣 Korean script you can use**")
        st.code(result["korean_script"], language=None)

    # Clarifying questions
    if result.get("clarifying_questions"):
        st.markdown("**❓ To help you better, could you clarify:**")
        for q in result["clarifying_questions"]:
            st.markdown(f"- {q}")

    # Escalation
    if result.get("escalation_contact"):
        st.markdown(f"**📞 Official contact:** {result['escalation_contact']}")

    # Sources
    srcs = result.get("_retrieved_sources", [])
    st.markdown(f"**📚 Sources used ({len(result.get('source_ids', []))} cited)**")
    cited = set(result.get("source_ids", []))
    if not srcs:
        st.caption("No sources in the knowledge base matched this question.")
    org_sourced = any(s.get("_is_org") for s in srcs)
    if org_sourced:
        st.caption("Includes information published by organizations via KOREA-LIFE Connect (marked below).")
    for s in srcs:
        if s["id"] in cited or not cited:
            ui.source_citation(s)

    # ---- Route to an organization (human assistance) ----
    st.divider()
    st.subheader("🏛 Need a person to help?")
    st.caption(
        "Send this question to a relevant organization on KOREA-LIFE Connect. They can reply with "
        "human assistance. Please don't include passport/ID or card numbers."
    )
    suggested = connect.suggest_org_for(query, city=profile.get("city", ""), retrieved_sources=srcs)
    orgs = database.list_organizations()
    if not orgs:
        st.caption("No organizations are available in this demo.")
    else:
        names = [o["name"] for o in orgs]
        default_idx = names.index(suggested["name"]) if suggested and suggested["name"] in names else 0
        pick = st.selectbox("Organization", names, index=default_idx, key="inq_org")
        msg = st.text_area("Message to the organization", value=query, key="inq_msg", height=80)
        if st.button("Send inquiry", key="send_inq"):
            org = next(o for o in orgs if o["name"] == pick)
            database.add_inquiry(
                org_id=org["id"], message=msg,
                requester_label=connect.requester_label(profile),
                topic=connect.classify_topic(query), source="copilot",
                is_demo=bool(profile.get("is_demo")),
            )
            st.success(f"Sent to {pick}. They'll see it in their KOREA-LIFE Connect inbox (demo).")

    # Action steps -> reminders
    steps = result.get("action_steps", [])
    if steps:
        st.divider()
        st.subheader("✅ Turn action steps into tracked reminders")
        st.caption(
            "Review each step. You confirm the due date before anything is saved. "
            "Saved items are **personal reminders**, not statutory deadlines."
        )
        from datetime import date, timedelta

        for i, step in enumerate(steps):
            with st.container(border=True):
                st.markdown(f"**{step.get('title','')}**")
                if step.get("detail"):
                    st.caption(step["detail"])
                c1, c2, c3 = st.columns([1.2, 1, 1])
                with c1:
                    due = st.date_input(
                        "Due date (you confirm)",
                        value=date.today() + timedelta(days=7),
                        key=f"step_due_{i}",
                    )
                with c2:
                    cat = step.get("suggested_category", "task")
                    if cat not in reminders.CATEGORIES:
                        cat = "task"
                    category = st.selectbox(
                        "Category",
                        reminders.CATEGORIES,
                        index=reminders.CATEGORIES.index(cat),
                        format_func=reminders.category_label,
                        key=f"step_cat_{i}",
                    )
                with c3:
                    st.write("")
                    st.write("")
                    if st.button("➕ Save reminder", key=f"step_save_{i}"):
                        database.add_reminder(
                            title=step.get("title", "Task"),
                            category=category,
                            due_date=due.isoformat(),
                            reminder_offsets=step.get("suggested_offset_days") or reminders.default_offsets_for(category),
                            notes=step.get("detail", ""),
                            source_ids=result.get("source_ids", []),
                            created_from="ai",
                            is_statutory=False,
                        )
                        st.success("Saved to your Life Plan & Life Manager (as a personal reminder).")

    with st.expander("🔎 Raw structured response (JSON)"):
        shown = {k: v for k, v in result.items() if not k.startswith("_retrieved")}
        st.json(shown)
