"""Shared Streamlit UI helpers and the KOREA-LIFE visual system ("official
portal" theme): CSS injection, dark sidebar, page headers, stat cards, the
trust band, reminder/record cards, source citations, onboarding, and the
notification badge. Kept here so every page stays short and consistent.
"""
from __future__ import annotations

import html
import json
from datetime import date
from typing import Any, Dict, List, Optional

import streamlit as st

from . import config, connect, database, reminders
from .i18n import LANGUAGES

APP_NAME = "KOREA-LIFE"

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
  :root{
    --ink:#111826; --ink2:#243143; --muted:#5a6678; --faint:#8a94a6;
    --line:#dde3ec; --line2:#e9edf3; --panel:#ffffff;
    --accent:#1d4ed8; --accent-deep:#14245e; --accent-soft:#eef3fd;
    --verify:#0f766e; --verify-soft:#e7f3f1;
    --danger:#b42318; --danger-soft:#fdeceb; --warn:#b45309; --warn-soft:#fdf3e7;
    --ok:#15803d; --ok-soft:#ecf6ef;
    --serif:'Iowan Old Style','Palatino Linotype',Georgia,'Times New Roman',serif;
  }
  html, body, [class*="css"] { font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }
  .stApp { background:#eceff4; }
  .block-container { padding-top:2.1rem; max-width:1200px; }

  /* ---- Dark institutional sidebar ---- */
  section[data-testid="stSidebar"]{ background:#0c1a2b; border-right:1px solid #16263d; }
  section[data-testid="stSidebar"] *{ color:#aeb9ca; }
  section[data-testid="stSidebar"] h1,
  section[data-testid="stSidebar"] h2,
  section[data-testid="stSidebar"] h3,
  section[data-testid="stSidebar"] strong{ color:#ffffff; }
  section[data-testid="stSidebar"] a{ color:#9fc0ff !important; }
  section[data-testid="stSidebar"] [data-testid="stAlert"]{ background:#11203c; border:1px solid #1f3355; color:#cdd9ea; }
  section[data-testid="stSidebar"] hr{ border-color:#1c2c45; }

  /* ---- Header / hero ---- */
  .kl-eyebrow{ font-size:11px; letter-spacing:1px; text-transform:uppercase; color:var(--accent); font-weight:700; }
  .kl-head{ border-bottom:1px solid var(--line); padding-bottom:16px; margin-bottom:20px; }
  .kl-head h1{ font-family:var(--serif); font-weight:600; font-size:25px; margin:6px 0 0; letter-spacing:-.2px; color:var(--ink); }
  .kl-head p{ color:var(--muted); font-size:13.5px; margin:5px 0 0; }
  .kl-utility{ display:flex; align-items:center; gap:8px; background:#fff; border:1px solid var(--line); border-left:3px solid var(--verify);
     border-radius:9px; padding:9px 14px; font-size:12.5px; color:var(--ink2); margin-bottom:18px; }

  /* ---- Badges / pills ---- */
  .kl-badge{ display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:7px; font-size:11.5px; font-weight:600; }
  .kl-live{ background:var(--accent-soft); color:var(--accent-deep); border:1px solid #cfe0fb; }
  .kl-fallback{ background:var(--accent-soft); color:var(--accent-deep); border:1px solid #cfe0fb; }
  .kl-demo{ background:var(--warn-soft); color:var(--warn); border:1px solid #f6dcb5; }
  .kl-verify{ background:var(--verify-soft); color:var(--verify); border:1px solid #c7e6e0; }
  .kl-dot{ width:7px; height:7px; border-radius:50%; background:currentColor; }

  /* ---- Stat cards ---- */
  .kl-stats{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin-bottom:20px; }
  .kl-stat{ background:var(--panel); border:1px solid var(--line); border-radius:11px; padding:15px 17px; position:relative;
     box-shadow:0 1px 2px rgba(16,24,40,.05); }
  .kl-stat::before{ content:""; position:absolute; left:17px; right:17px; top:0; height:2px; border-radius:0 0 3px 3px; }
  .kl-stat.red::before{ background:var(--danger);} .kl-stat.amber::before{ background:var(--warn);}
  .kl-stat.blue::before{ background:var(--accent);} .kl-stat.green::before{ background:var(--ok);}
  .kl-stat .lab{ font-size:11.5px; color:var(--muted); font-weight:700; letter-spacing:.4px; text-transform:uppercase; }
  .kl-stat .num{ font-size:30px; font-weight:800; letter-spacing:-1px; margin-top:10px; line-height:1; color:var(--ink); }
  .kl-stat.red .num{ color:var(--danger);} .kl-stat.amber .num{ color:var(--warn);}
  .kl-stat.blue .num{ color:var(--accent);} .kl-stat.green .num{ color:var(--ok);}
  .kl-stat .foot{ font-size:11.5px; color:var(--faint); margin-top:6px; }

  /* ---- Trust band ---- */
  .kl-band{ background:var(--panel); border:1px solid var(--line); border-radius:11px; padding:15px 18px; margin-bottom:22px;
     box-shadow:0 1px 2px rgba(16,24,40,.05); }
  .kl-band .bt{ font-size:12.5px; font-weight:700; color:var(--ink2); }
  .kl-band .bt .muted{ font-weight:500; color:var(--muted); }
  .kl-srcs{ display:flex; flex-wrap:wrap; gap:8px; margin-top:11px; }
  .kl-chip{ font-size:11.5px; color:var(--ink2); background:#f6f8fb; border:1px solid var(--line2); border-radius:7px;
     padding:5px 10px; display:inline-flex; align-items:center; gap:6px; }
  .kl-chip .vk{ width:6px; height:6px; border-radius:50%; background:var(--verify); }
  .kl-chip.org .vk{ background:var(--accent); }

  /* ---- Record / reminder cards ---- */
  .kl-rec{ background:var(--panel); border:1px solid var(--line); border-radius:11px; padding:13px 16px; margin-bottom:10px;
     position:relative; box-shadow:0 1px 2px rgba(16,24,40,.04); }
  .kl-rec::before{ content:""; position:absolute; left:0; top:13px; bottom:13px; width:4px; border-radius:4px; background:var(--accent); }
  .kl-rec.red::before{ background:var(--danger);} .kl-rec.amber::before{ background:var(--warn);}
  .kl-rec.blue::before{ background:var(--accent);} .kl-rec.green::before{ background:var(--ok); }
  .kl-rec .hd{ display:flex; align-items:center; gap:10px; flex-wrap:wrap; }
  .kl-rec .ti{ font-weight:700; font-size:14px; color:var(--ink); }
  .kl-rec .cd{ margin-left:auto; font-size:12px; font-weight:700; color:var(--ink2); text-align:right; white-space:nowrap; }
  .kl-rec .cd span{ display:block; font-size:10.5px; font-weight:500; color:var(--faint); }
  .kl-tag{ font-size:10px; font-weight:700; letter-spacing:.3px; text-transform:uppercase; padding:3px 8px; border-radius:5px;
     background:#eef1f6; color:#5b6676; border:1px solid var(--line2); }
  .kl-tag.verify{ background:var(--verify-soft); color:var(--verify); border-color:#c7e6e0; }
  .kl-rec .meta{ font-size:12px; color:var(--muted); margin-top:9px; }
  .kl-rec .meta b{ color:var(--ink2); font-weight:600; }
  .kl-rec .note{ font-size:12px; color:#8691a6; margin-top:7px; }

  /* ---- Source citation ---- */
  .kl-src{ background:#f7f9fc; border:1px solid var(--line2); border-left:3px solid var(--verify); border-radius:9px;
     padding:11px 14px; margin:8px 0; font-size:13px; }
  .kl-src.org{ border-left-color:var(--accent); }
  .kl-src .sid{ font-weight:700; color:var(--ink2); }
  .kl-src .meta{ color:var(--muted); font-size:11.5px; }

  /* ---- Empty state ---- */
  .kl-empty{ background:var(--panel); border:1px dashed #d4dbe6; border-radius:11px; padding:26px 18px; text-align:center; }
  .kl-empty .t{ font-weight:700; font-size:13.5px; color:var(--ink2); }
  .kl-empty .s{ color:var(--muted); font-size:12px; margin-top:4px; }

  /* ---- Buttons ---- */
  .stButton>button{ border-radius:8px; border:1px solid var(--line); font-weight:600; font-size:13px; }
  .stButton>button[kind="primary"]{ background:var(--accent); border-color:var(--accent); }

  /* ---- Metrics (Streamlit native, used on some pages) ---- */
  [data-testid="stMetric"]{ background:#fff; border:1px solid var(--line); border-radius:11px; padding:14px 16px; }
  [data-testid="stMetricValue"]{ font-weight:800; }

  .kl-note{ font-size:12px; color:var(--muted); border-top:1px solid var(--line); padding-top:14px; margin-top:22px; }
</style>
"""


def inject_css() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def ensure_db() -> None:
    database.init_db()
    # Seed the (clearly-labeled) demo organizations for KOREA-LIFE Connect.
    try:
        connect.seed_demo()
    except Exception:
        pass


def get_profile() -> Optional[Dict[str, Any]]:
    return database.get_profile()


def _esc(s: Any) -> str:
    return html.escape(str(s if s is not None else ""))


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
def page_header(eyebrow: str, title: str, subtitle: str = "") -> None:
    st.markdown(
        f"<div class='kl-head'><div class='kl-eyebrow'>{_esc(eyebrow)}</div>"
        f"<h1>{_esc(title)}</h1>"
        + (f"<p>{_esc(subtitle)}</p>" if subtitle else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str = "") -> None:
    # Backwards-compatible alias used by some pages.
    page_header("KOREA-LIFE", title, subtitle)


def utility_bar(text: str) -> None:
    st.markdown(f"<div class='kl-utility'>🛡 {_esc(text)}</div>", unsafe_allow_html=True)


def mode_badge() -> str:
    if config.ai_enabled():
        return "<span class='kl-badge kl-live'><span class='kl-dot'></span> AI · live Claude</span>"
    return "<span class='kl-badge kl-fallback'><span class='kl-dot'></span> AI · offline demo</span>"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def sidebar_status() -> Optional[Dict[str, Any]]:
    profile = get_profile()
    with st.sidebar:
        st.markdown(f"### 🇰🇷 {APP_NAME}")
        st.caption("Resident Information Portal")
        st.markdown(mode_badge(), unsafe_allow_html=True)
        if profile:
            demo = " · DEMO" if profile.get("is_demo") else ""
            st.markdown(
                f"**{LANGUAGES.get(profile.get('language','en'),'English')}**  \n"
                f"{profile.get('resident_type','—')} · {profile.get('city','—')}{demo}"
            )
            summary = reminders.run_reminder_check()
            if summary["notifications"]:
                st.warning(
                    f"🔔 {summary['notifications']} reminder(s) need attention — "
                    f"{summary['overdue']} overdue, {summary['today']} today, {summary['due_soon']} due soon"
                )
            else:
                st.success("🔔 No reminders need attention.")
        else:
            st.info("Complete onboarding on the Home page to begin.")
        st.divider()
        st.caption(
            "Navigation aid only — not legal, immigration, labor, healthcare, or "
            "financial advice. Verify with official sources."
        )
    return profile


# ---------------------------------------------------------------------------
# Dashboard components
# ---------------------------------------------------------------------------
def stat_cards(cards: List[Dict[str, Any]]) -> None:
    """cards: list of {label, value, foot, tone} where tone in red/amber/blue/green."""
    items = ""
    for c in cards:
        items += (
            f"<div class='kl-stat {c.get('tone','blue')}'>"
            f"<div class='lab'>{_esc(c['label'])}</div>"
            f"<div class='num'>{_esc(c['value'])}</div>"
            f"<div class='foot'>{_esc(c.get('foot',''))}</div></div>"
        )
    st.markdown(f"<div class='kl-stats'>{items}</div>", unsafe_allow_html=True)


def trust_band() -> None:
    from . import knowledge

    official = knowledge.all_sources()
    org_count = database.count_organizations()
    chips = ""
    for s in official:
        chips += f"<span class='kl-chip'><span class='vk'></span>{_esc(s['issuer'])}</span>"
    if org_count:
        chips += (
            f"<span class='kl-chip org'><span class='vk'></span>"
            f"{org_count} organization(s) via KOREA-LIFE Connect</span>"
        )
    st.markdown(
        "<div class='kl-band'><div class='bt'>🛡 Grounded in "
        f"{len(official)} official sources"
        "<span class='muted'> · citations shown with every answer"
        + (" · plus verified organization info" if org_count else "")
        + "</span></div>"
        f"<div class='kl-srcs'>{chips}</div></div>",
        unsafe_allow_html=True,
    )


def record_card(r: Dict[str, Any]) -> None:
    """Read-only styled record (used on the Home dashboard)."""
    status = r.get("_status") or reminders.compute_display_status(r)
    days = r.get("_days_until")
    if days is None:
        days = reminders.days_until(r.get("due_date", ""))
    tone = {
        reminders.STATUS_OVERDUE: "red", reminders.STATUS_TODAY: "amber",
        reminders.STATUS_DUE_SOON: "blue", reminders.STATUS_COMPLETED: "green",
    }.get(status, "blue")
    icon = reminders.category_icon(r.get("category", "other"))
    label = reminders.category_label(r.get("category", "other"))
    tag = ("<span class='kl-tag verify'>verified deadline</span>" if r.get("is_statutory")
           else "<span class='kl-tag'>personal</span>")
    offs = r.get("reminder_offsets") or []
    offs_txt = " · ".join(str(o) for o in offs) + " day alerts" if offs else ""
    amount = r.get("amount")
    amount_txt = f" · {amount:,.0f} {r.get('currency','KRW')}" if amount else ""
    st.markdown(
        f"<div class='kl-rec {tone}'>"
        f"<div class='hd'><span class='ti'>{icon} {_esc(r.get('title',''))}</span>{tag}"
        f"<span class='cd'>{_esc(r.get('due_date',''))}<span>{_esc(_countdown_text(days, status))}</span></span></div>"
        f"<div class='meta'>Category <b>{_esc(label)}</b>{amount_txt}"
        + (f" · Advance alerts <b>{_esc(offs_txt)}</b>" if offs_txt else "")
        + "</div>"
        + (f"<div class='note'>📝 {_esc(r.get('notes'))}</div>" if r.get("notes") else "")
        + "</div>",
        unsafe_allow_html=True,
    )


def empty_state(title: str, sub: str = "") -> None:
    st.markdown(
        f"<div class='kl-empty'><div class='t'>{_esc(title)}</div>"
        + (f"<div class='s'>{_esc(sub)}</div>" if sub else "")
        + "</div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------
def onboarding_form(prefill: Optional[Dict[str, Any]] = None) -> None:
    prefill = prefill or {}
    st.subheader("Your profile")
    st.caption(
        "We only collect what helps tailor guidance. We never ask for your passport "
        "or residence-card numbers, bank details, or other sensitive identifiers."
    )
    with st.form("onboarding"):
        lang_codes = list(LANGUAGES.keys())
        language = st.selectbox(
            "Preferred language", lang_codes,
            index=lang_codes.index(prefill.get("language", "en")) if prefill.get("language") in lang_codes else 0,
            format_func=lambda c: LANGUAGES[c],
        )
        resident_types = ["student", "employee", "job seeker", "entrepreneur", "family", "other"]
        rt_default = prefill.get("resident_type", "student")
        resident_type = st.selectbox(
            "Resident type", resident_types,
            index=resident_types.index(rt_default) if rt_default in resident_types else 0,
        )
        city = st.text_input("City / Province", value=prefill.get("city", ""), placeholder="e.g. Seoul, Busan, Gyeonggi")
        residence_category = st.text_input(
            "Residence category (optional)", value=prefill.get("residence_category", ""),
            placeholder="e.g. D-2, E-7, F-6 — category only, never a number",
            help="Optional. Enter only the category label (like D-2), never your card number.",
        )
        st.markdown("**Important dates (optional)** — personal reminders you want tracked")
        existing = prefill.get("important_dates", [])
        dates_text = "\n".join(f"{d.get('label','')} | {d.get('date','')}" for d in existing)
        raw_dates = st.text_area(
            "One per line as:  label | YYYY-MM-DD", value=dates_text,
            placeholder="Lease renewal | 2026-12-20\nResidence card expiry | 2027-03-15", height=90,
        )
        submitted = st.form_submit_button("Save profile", type="primary")

    if submitted:
        important_dates, errors = _parse_important_dates(raw_dates)
        if not city.strip():
            st.error("Please enter your city or province.")
            return
        if errors:
            st.error("Some dates could not be read (use YYYY-MM-DD): " + "; ".join(errors))
            return
        database.save_profile(
            language=language, resident_type=resident_type, city=city.strip(),
            residence_category=residence_category.strip(), important_dates=important_dates,
            is_demo=bool(prefill.get("is_demo", False)) and prefill.get("city") == city.strip(),
        )
        if important_dates:
            _create_reminders_from_important_dates(important_dates)
        st.success("Profile saved.")
        st.rerun()


def _parse_important_dates(raw: str):
    from datetime import datetime

    items: List[Dict[str, str]] = []
    errors: List[str] = []
    for line in (raw or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if "|" not in line:
            errors.append(line)
            continue
        label, _, value = line.partition("|")
        value = value.strip()
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            errors.append(line)
            continue
        items.append({"label": label.strip() or "Important date", "date": value})
    return items, errors


def _create_reminders_from_important_dates(items: List[Dict[str, str]]) -> None:
    existing = {(r["title"], r["due_date"]) for r in database.list_reminders()}
    for item in items:
        key = (item["label"], item["date"])
        if key in existing:
            continue
        category = "other"
        low = item["label"].lower()
        if "card" in low or "arc" in low:
            category = "residence_card"
        elif "passport" in low:
            category = "passport"
        elif "lease" in low or "rent" in low:
            category = "rent"
        elif "visa" in low:
            category = "visa"
        database.add_reminder(
            title=item["label"], category=category, due_date=item["date"],
            reminder_offsets=reminders.default_offsets_for(category),
            notes="Created from your onboarding important dates.", created_from="manual",
        )


def load_demo_profile() -> None:
    with open(config.DEMO_PROFILE_PATH, "r", encoding="utf-8") as fh:
        demo = json.load(fh)
    database.save_profile(
        language=demo.get("language", "en"), resident_type=demo.get("resident_type", "employee"),
        city=demo.get("city", "Seoul"), residence_category=demo.get("residence_category", ""),
        important_dates=demo.get("important_dates", []), is_demo=True,
    )
    _create_reminders_from_important_dates(demo.get("important_dates", []))


# ---------------------------------------------------------------------------
# Interactive reminder card (Life Manager / Life Plan)
# ---------------------------------------------------------------------------
def reminder_card(r: Dict[str, Any], *, key_prefix: str, show_actions: bool = True) -> None:
    record_card(r)
    if not show_actions:
        return
    status = r.get("_status") or reminders.compute_display_status(r)
    rid = r["id"]
    if status == reminders.STATUS_COMPLETED:
        if st.button("↩ Reopen", key=f"{key_prefix}_reopen_{rid}"):
            reminders.reopen_reminder(rid)
            st.rerun()
        return
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        if st.button("✓ Mark paid/done", key=f"{key_prefix}_done_{rid}"):
            new_id = reminders.complete_reminder(rid)
            st.toast("Completed. Next recurring reminder created." if new_id else "Marked complete.")
            st.rerun()
    with c2:
        if st.button("Snooze 3d", key=f"{key_prefix}_snooze_{rid}"):
            reminders.snooze_reminder(rid, 3)
            st.rerun()
    with c3:
        if st.button("Dismiss", key=f"{key_prefix}_dismiss_{rid}"):
            reminders.dismiss_reminder(rid)
            st.rerun()
    with c4:
        if st.button("Delete", key=f"{key_prefix}_del_{rid}"):
            database.delete_reminder(rid)
            st.rerun()


def _countdown_text(days: Optional[int], status: str) -> str:
    if status == reminders.STATUS_COMPLETED:
        return "completed"
    if days is None:
        return ""
    if days < 0:
        return f"{abs(days)} day(s) overdue"
    if days == 0:
        return "due today"
    return f"in {days} day(s)"


def source_citation(source: Dict[str, Any]) -> None:
    is_org = source.get("_is_org")
    cls = "kl-src org" if is_org else "kl-src"
    url_line = (
        f"🔗 <a href='{_esc(source['url'])}' target='_blank'>{_esc(source['url'])}</a> · "
        if source.get("url") else ""
    )
    kind = "organization (verified, demo)" if is_org else "official source"
    st.markdown(
        f"<div class='{cls}'><span class='sid'>[{_esc(source['id'])}] {_esc(source['title'])}</span>"
        f" <span class='meta'>· {kind}</span><br>"
        f"<span class='meta'>Issuer: {_esc(source['issuer'])} · {_esc(source.get('geography',''))}</span><br>"
        f"{_esc(source.get('verified_summary',''))}<br>"
        f"<span class='meta'>{url_line}📞 {_esc(source.get('escalation_contact',''))} · "
        f"last checked {_esc(source.get('last_checked',''))}</span></div>",
        unsafe_allow_html=True,
    )
