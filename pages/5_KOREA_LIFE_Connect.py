"""KOREA-LIFE Connect — the institutional side of the platform (landing).

Explains the two-sided model and lets a visitor enter an organization's console
(as a clearly-labeled demo). This is where universities, employers, and support
organizations would manage their presence on the platform.
"""
from __future__ import annotations

import streamlit as st

from korealife import connect, database, ui

st.set_page_config(page_title="KOREA-LIFE Connect", page_icon="🏛️", layout="wide")
ui.inject_css()
ui.ensure_db()
ui.sidebar_status()

ui.page_header("KOREA-LIFE Connect", "The institutional side of the platform",
               "How universities, employers, and support organizations connect with foreign residents.")
ui.utility_bar("Simulated institutional portal — all organization data shown here is synthetic demo data.")

st.markdown(
    "KOREA-LIFE is a **two-sided ecosystem**. Residents use the assistant and Life Manager; "
    "institutions use **Connect** to publish verified information and help people directly. "
    "The two sides are linked:"
)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("##### 1 · Publish")
    st.caption("Organizations publish verified procedures, FAQs, and requirements about their own services.")
with c2:
    st.markdown("##### 2 · Surface")
    st.caption("That verified info is retrieved and **cited** by the AI assistant when it's relevant to a resident's question.")
with c3:
    st.markdown("##### 3 · Assist")
    st.caption("Residents can route a question to the organization, which manages inquiries and sees anonymized trends.")

st.divider()
st.subheader("Participating organizations (demo)")
st.caption("Synthetic sample organizations. No real partnerships exist; no real government integrations.")

orgs = database.list_organizations()
if not orgs:
    st.info("No organizations seeded.")
else:
    cols = st.columns(len(orgs) if len(orgs) <= 3 else 3)
    for i, org in enumerate(orgs):
        with cols[i % len(cols)]:
            typ = connect.ORG_TYPES.get(org["org_type"], org["org_type"])
            verified = "🟢 Verified (demo)" if org.get("verified") else "—"
            res_count = len(database.list_org_resources(org_id=org["id"], only_published=True))
            inq_count = len(database.list_inquiries(org_id=org["id"]))
            st.markdown(
                f"<div class='kl-rec blue'><div class='hd'><span class='ti'>{org['name']}</span></div>"
                f"<div class='meta'>{typ} · {org.get('city','')} · {verified}<br>"
                f"<b>{res_count}</b> published items · <b>{inq_count}</b> inquiries</div>"
                f"<div class='note'>{org.get('description','')}</div></div>",
                unsafe_allow_html=True,
            )
            if st.button(f"Open console as this org →", key=f"open_{org['id']}"):
                st.session_state["connect_org_id"] = org["id"]
                st.switch_page("pages/6_Institution_Console.py")

st.markdown(
    "<div class='kl-note'>KOREA-LIFE Connect is a demonstration of the institutional model. "
    "It does not integrate with real government systems and does not claim real partnerships. "
    "All organizations and their content are synthetic.</div>",
    unsafe_allow_html=True,
)
