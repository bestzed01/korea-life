"""KOREA-LIFE Connect — Institution Console (demo).

The organization-facing dashboard: manage the profile, publish verified
procedures/FAQs/requirements (which feed the AI assistant), handle inquiries
that need a human, and view privacy-protected aggregate trends.
"""
from __future__ import annotations

import streamlit as st

from korealife import connect, database, ui

st.set_page_config(page_title="Institution Console · KOREA-LIFE Connect", page_icon="🏢", layout="wide")
ui.inject_css()
ui.ensure_db()
ui.sidebar_status()

orgs = database.list_organizations()
if not orgs:
    st.warning("No organizations available. Open KOREA-LIFE Connect first.")
    st.stop()

# "Acting as" org selector
names = [o["name"] for o in orgs]
default_id = st.session_state.get("connect_org_id", orgs[0]["id"])
default_idx = next((i for i, o in enumerate(orgs) if o["id"] == default_id), 0)

ui.page_header("KOREA-LIFE Connect", "Institution Console",
               "Manage your organization's verified information, inquiries, and insights.")
ui.utility_bar("Demo console — you are acting as a synthetic sample organization.")

acting = st.selectbox("You are acting as", names, index=default_idx)
org = next(o for o in orgs if o["name"] == acting)
st.session_state["connect_org_id"] = org["id"]
typ = connect.ORG_TYPES.get(org["org_type"], org["org_type"])
st.caption(f"{typ} · {org.get('city','')} · {'🟢 Verified (demo)' if org.get('verified') else 'Unverified'}")

tab_prof, tab_pub, tab_inq, tab_ins = st.tabs(
    ["🏢 Profile", "📄 Published info", "📨 Inquiries", "📊 Insights"]
)

# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------
with tab_prof:
    with st.form("org_profile"):
        name = st.text_input("Organization name", value=org["name"])
        types = list(connect.ORG_TYPES.keys())
        org_type = st.selectbox("Type", types, index=types.index(org["org_type"]) if org["org_type"] in types else 0,
                                format_func=lambda t: connect.ORG_TYPES[t])
        city = st.text_input("City / Province", value=org.get("city", ""))
        contact = st.text_input("Contact email (demo)", value=org.get("contact_email", ""))
        desc = st.text_area("Description", value=org.get("description", ""), height=90)
        saved = st.form_submit_button("Save profile", type="primary")
    if saved:
        database.update_organization(org["id"], name=name, org_type=org_type, city=city,
                                     contact_email=contact, description=desc)
        st.success("Profile updated.")
        st.rerun()

# ---------------------------------------------------------------------------
# Published info (feeds the AI assistant)
# ---------------------------------------------------------------------------
with tab_pub:
    st.caption(
        "Published items are retrieved and **cited** by the AI assistant when relevant to a resident's "
        "question. Keep them factual and about your own services. Mark immigration/legal specifics as "
        "referrals to official bodies."
    )
    resources = database.list_org_resources(org_id=org["id"])
    st.markdown(f"**{len([r for r in resources if r['status']=='published'])} published · {len(resources)} total**")

    for r in resources:
        badge = "🟢 published" if r["status"] == "published" else "⚪ draft"
        with st.expander(f"{badge} · [{r['resource_type']}] {r['title']}"):
            with st.form(f"res_{r['id']}"):
                title = st.text_input("Title", value=r["title"], key=f"rt_{r['id']}")
                rtypes = ["procedure", "faq", "requirement"]
                rtype = st.selectbox("Type", rtypes, index=rtypes.index(r["resource_type"]) if r["resource_type"] in rtypes else 1, key=f"rty_{r['id']}")
                body = st.text_area("Content", value=r.get("body", ""), height=120, key=f"rb_{r['id']}")
                topic_opts = list(connect.TOPIC_BUCKETS.keys())
                topics = st.multiselect("Topics", topic_opts, default=[t for t in r.get("topic", []) if t in topic_opts], key=f"rto_{r['id']}")
                published = st.checkbox("Published (visible to the assistant)", value=r["status"] == "published", key=f"rp_{r['id']}")
                c1, c2 = st.columns(2)
                save = c1.form_submit_button("Save")
                delete = c2.form_submit_button("Delete")
            if save:
                database.update_org_resource(r["id"], title=title, resource_type=rtype, body=body,
                                              topic=topics, status="published" if published else "draft")
                st.success("Saved.")
                st.rerun()
            if delete:
                database.delete_org_resource(r["id"])
                st.rerun()

    st.divider()
    st.markdown("**Add a new item**")
    with st.form("new_res"):
        ntitle = st.text_input("Title", placeholder="e.g. How to request a transcript")
        nrtypes = ["procedure", "faq", "requirement"]
        nrtype = st.selectbox("Type", nrtypes, format_func=str.title)
        nbody = st.text_area("Content", height=110, placeholder="Describe your own verified procedure / FAQ / requirement.")
        ntopics = st.multiselect("Topics", list(connect.TOPIC_BUCKETS.keys()))
        npublished = st.checkbox("Publish immediately", value=True)
        add = st.form_submit_button("Add item", type="primary")
    if add:
        if not ntitle.strip() or not nbody.strip():
            st.error("Title and content are required.")
        else:
            database.add_org_resource(org_id=org["id"], title=ntitle, resource_type=nrtype, body=nbody,
                                      topic=ntopics, languages=org.get("languages", []),
                                      status="published" if npublished else "draft", is_demo=True)
            st.success("Added.")
            st.rerun()

# ---------------------------------------------------------------------------
# Inquiries
# ---------------------------------------------------------------------------
with tab_inq:
    st.caption("Inquiries routed to your organization from residents via the assistant. No passport/ID or card numbers are collected.")
    inquiries = database.list_inquiries(org_id=org["id"])
    statuses = ["new", "in_progress", "resolved", "closed"]
    counts = {s: sum(1 for i in inquiries if i["status"] == s) for s in statuses}
    m = st.columns(4)
    m[0].metric("New", counts["new"])
    m[1].metric("In progress", counts["in_progress"])
    m[2].metric("Resolved", counts["resolved"])
    m[3].metric("Closed", counts["closed"])

    if not inquiries:
        ui.empty_state("No inquiries yet", "When a resident sends a question from the assistant, it appears here.")
    for inq in inquiries:
        demo = " · demo" if inq.get("is_demo") else ""
        with st.expander(f"[{inq['status']}] {inq.get('topic','general')} — {inq.get('requester_label','Resident')}{demo}"):
            st.markdown(f"**Question:** {inq['message']}")
            st.caption(f"Received {inq.get('created_at','')[:16].replace('T',' ')} · via {inq.get('source','')}")
            with st.form(f"inq_{inq['id']}"):
                new_status = st.selectbox("Status", statuses, index=statuses.index(inq["status"]) if inq["status"] in statuses else 0, key=f"is_{inq['id']}")
                response = st.text_area("Response to resident", value=inq.get("response", "") or "", key=f"ir_{inq['id']}", height=90)
                upd = st.form_submit_button("Update inquiry")
            if upd:
                database.update_inquiry(inq["id"], status=new_status, response=response)
                st.success("Updated.")
                st.rerun()

# ---------------------------------------------------------------------------
# Insights (privacy-protected aggregates)
# ---------------------------------------------------------------------------
with tab_ins:
    st.caption(
        "Aggregated, privacy-protected trends in what residents are asking across the platform. "
        "No personal data, no raw question text — only topic, coarse city, and language counts."
    )
    data = connect.trends()
    st.metric("Total questions logged (anonymized)", data["total"])

    st.markdown("**Top question topics**")
    if data["by_topic"]:
        topic_rows = {k.replace("_", " ").title(): v for k, v in data["by_topic"]}
        st.bar_chart(topic_rows, horizontal=True, color="#1d4ed8")
    else:
        st.caption("No data yet.")

    colA, colB = st.columns(2)
    with colA:
        st.markdown("**By language**")
        if data["by_language"]:
            st.bar_chart({k.upper(): v for k, v in data["by_language"]})
        else:
            st.caption("No data yet.")
    with colB:
        st.markdown("**By city (coarse)**")
        if data["by_city"]:
            st.bar_chart({k: v for k, v in data["by_city"]})
        else:
            st.caption("No data yet.")

    st.markdown("**Question volume — last 14 days**")
    st.line_chart({"questions": list(data["volume_by_day"].values())})
    st.caption("Demo analytics. Counts combine seeded synthetic data with anonymized logs from this session.")

st.markdown(
    "<div class='kl-note'>KOREA-LIFE Connect is a demonstration. Organization data is synthetic, there are no "
    "real government integrations, and no real partnerships are implied.</div>",
    unsafe_allow_html=True,
)
