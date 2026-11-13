"""KOREA-LIFE CONNECT — the institutional side of the platform.

This is the second layer of the two-sided ecosystem. Organizations
(universities, employers, support organizations) maintain a profile, publish
verified procedures / FAQs / requirements, receive inquiries that need a human,
and view privacy-protected aggregate trends in resident questions.

The link to the foreigner-facing assistant:
- published org resources are exposed as retrievable "sources" (so the AI can
  cite an organization's own verified procedure when it's relevant);
- the assistant can route a question to a relevant organization as an inquiry;
- each assistant question is logged as an anonymized topic bucket for trends.

ALL organization data in this prototype is synthetic demo data, clearly labeled.
There are no real government integrations and no real partnerships.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from . import database

ORG_TYPES = {
    "university": "University",
    "employer": "Employer",
    "support": "Support organization",
}

# Map a free-text topic to a coarse bucket used for retrieval + trends.
TOPIC_BUCKETS = {
    "immigration": ["visa", "immigration", "stay", "extend", "residence", "card", "arc", "reentry", "appointment", "sojourn"],
    "health": ["health", "insurance", "nhis", "premium", "medical", "hospital", "clinic"],
    "labor": ["work", "job", "labor", "labour", "employer", "wage", "salary", "contract", "payroll", "overtime"],
    "education": ["student", "university", "enrol", "enroll", "tuition", "course", "dormitory", "campus", "d-2"],
    "daily_life": ["housing", "rent", "bank", "phone", "transport", "settle", "community", "life"],
}


def classify_topic(text: str) -> str:
    low = (text or "").lower()
    best, best_hits = "daily_life", 0
    for bucket, terms in TOPIC_BUCKETS.items():
        hits = sum(1 for t in terms if t in low)
        if hits > best_hits:
            best, best_hits = bucket, hits
    return best


# ---------------------------------------------------------------------------
# Seeding (idempotent): only seeds when there are no organizations yet.
# ---------------------------------------------------------------------------
def seed_demo(force: bool = False) -> None:
    if not force and database.count_organizations() > 0:
        return

    orgs = [
        {
            "name": "Hangang Global University (demo)",
            "org_type": "university",
            "city": "Seoul",
            "description": "Synthetic sample university used to demonstrate KOREA-LIFE Connect. Supports international students with enrollment, visa support liaison, and campus life.",
            "contact_email": "intl-office@demo.example",
            "languages": ["en", "ko", "zh"],
            "resources": [
                {"title": "How to request an enrollment certificate", "resource_type": "procedure",
                 "topic": ["education", "immigration"],
                 "body": "International students can request an official enrollment certificate from the International Office. Bring your student ID; processing typically takes 1–2 business days. The certificate is commonly used for immigration and banking. (Demo content — confirm current steps with the office.)"},
                {"title": "D-2 student visa support: what the office can and cannot do", "resource_type": "faq",
                 "topic": ["immigration", "education"],
                 "body": "The International Office can issue enrollment documents and guide you to the correct immigration procedure, but it cannot decide immigration outcomes. For visa rules and deadlines, the office refers students to HiKorea and the 1345 Immigration Contact Center. (Demo content.)"},
                {"title": "Dormitory application requirements", "resource_type": "requirement",
                 "topic": ["education", "daily_life"],
                 "body": "Dormitory applications require current enrollment and a completed health declaration. Application windows open before each semester. (Demo content — dates vary by semester.)"},
            ],
        },
        {
            "name": "Hangyo Tech Co. (demo)",
            "org_type": "employer",
            "city": "Seoul",
            "description": "Synthetic sample employer used to demonstrate KOREA-LIFE Connect. Employs foreign professionals and supports their onboarding.",
            "contact_email": "people-ops@demo.example",
            "languages": ["en", "ko"],
            "resources": [
                {"title": "New-hire onboarding checklist for foreign employees", "resource_type": "procedure",
                 "topic": ["labor", "daily_life"],
                 "body": "Onboarding covers your employment contract, payroll setup, and workplace orientation. HR will explain your contract terms and answer payroll questions. For statutory labor rights or disputes, HR points employees to the MOEL 1350 labor counseling line. (Demo content.)"},
                {"title": "Health insurance enrollment for employees", "resource_type": "faq",
                 "topic": ["health", "labor"],
                 "body": "Qualifying employees are enrolled in national health insurance through the employer. Your premium and bill schedule are individual; HR can help you read your NHIS notice but cannot change statutory amounts. (Demo content.)"},
            ],
        },
        {
            "name": "Seoul Newcomer Support Center (demo)",
            "org_type": "support",
            "city": "Seoul",
            "description": "Synthetic sample support organization used to demonstrate KOREA-LIFE Connect. Offers settling-in help, interpretation referrals, and community programs.",
            "contact_email": "help@demo.example",
            "languages": ["en", "ko", "ru", "uz"],
            "resources": [
                {"title": "Free settling-in counseling: what to expect", "resource_type": "faq",
                 "topic": ["daily_life"],
                 "body": "Walk-in and appointment counseling helps newcomers with housing, banking, and daily-life questions, with interpretation referrals available. For official immigration or labor matters, counselors connect residents to the relevant official channel. (Demo content.)"},
                {"title": "Interpretation support request procedure", "resource_type": "procedure",
                 "topic": ["daily_life", "immigration"],
                 "body": "Request interpretation support by contacting the center ahead of an office visit. Languages supported in this demo include English, Russian, and Uzbek. (Demo content.)"},
            ],
        },
    ]

    for od in orgs:
        oid = database.add_organization(
            name=od["name"], org_type=od["org_type"], city=od["city"],
            description=od["description"], contact_email=od["contact_email"],
            languages=od["languages"], verified=True, is_demo=True,
        )
        for r in od["resources"]:
            database.add_org_resource(
                org_id=oid, title=r["title"], resource_type=r["resource_type"],
                topic=r["topic"], body=r["body"], languages=od["languages"],
                status="published", is_demo=True,
            )

    _seed_demo_inquiries()
    _seed_demo_trends()


def _seed_demo_inquiries() -> None:
    orgs = database.list_organizations()
    by_type = {o["org_type"]: o for o in orgs}
    samples = [
        ("university", "Resident · student · Seoul", "education",
         "I need an enrollment certificate for my bank. How long does it take?", "resolved",
         "You can collect it from the International Office in 1–2 business days with your student ID.", "copilot"),
        ("university", "Resident · student · Seoul", "immigration",
         "Does the office help with my D-2 extension paperwork?", "in_progress", "", "copilot"),
        ("employer", "Resident · employee · Seoul", "labor",
         "Where can I see the breakdown of my payroll deductions?", "new", "", "copilot"),
        ("support", "Resident · job seeker · Seoul", "daily_life",
         "Can someone help me open a bank account? I need interpretation.", "new", "", "manual"),
    ]
    for otype, label, topic, msg, status, resp, source in samples:
        org = by_type.get(otype)
        if not org:
            continue
        inq_id = database.add_inquiry(
            org_id=org["id"], message=msg, requester_label=label, topic=topic,
            status=status, source=source, is_demo=True,
        )
        if resp:
            database.update_inquiry(inq_id, response=resp)


def _seed_demo_trends() -> None:
    """Seed anonymized aggregate question volume (topic/city/language only)."""
    import random

    rng = random.Random(42)
    cities = ["Seoul", "Busan", "Incheon", "Gyeonggi"]
    langs = ["en", "ru", "uz", "ko"]
    weights = {"immigration": 32, "health": 18, "labor": 20, "education": 16, "daily_life": 14}
    now = datetime.utcnow()
    for topic, count in weights.items():
        for _ in range(count):
            days_ago = rng.randint(0, 29)
            database.log_question(
                topic=topic,
                city=rng.choice(cities),
                language=rng.choice(langs),
                is_demo=True,
                created_at=(now - timedelta(days=days_ago)).isoformat(timespec="seconds"),
            )


# ---------------------------------------------------------------------------
# Retrieval adapter: published org resources -> source-shaped records
# ---------------------------------------------------------------------------
def published_resources_as_sources() -> List[Dict[str, Any]]:
    """Expose published org resources in the same shape as knowledge-base sources
    so the AI retriever can score and cite them alongside official sources."""
    orgs = {o["id"]: o for o in database.list_organizations()}
    out: List[Dict[str, Any]] = []
    for res in database.list_org_resources(only_published=True):
        org = orgs.get(res["org_id"])
        if not org:
            continue
        out.append({
            "id": f"ORG-{org['id']}-R{res['id']}",
            "title": f"{res['title']}",
            "issuer": f"{org['name']} · organization (demo)",
            "topic": res.get("topic", []),
            "geography": org.get("city", ""),
            "url": "",  # internal institutional content; no external URL
            "verified_summary": res.get("body", ""),
            "excerpts": [],
            "languages": res.get("languages", []),
            "escalation_contact": f"{org['name']} — {org.get('contact_email','')}",
            "last_checked": (res.get("updated_at") or "")[:10],
            "_org_id": org["id"],
            "_org_name": org["name"],
            "_is_org": True,
            "_resource_type": res.get("resource_type", "faq"),
        })
    return out


# ---------------------------------------------------------------------------
# Inquiry routing
# ---------------------------------------------------------------------------
def suggest_org_for(topic: str, city: str = "", retrieved_sources: Optional[List[Dict[str, Any]]] = None) -> Optional[Dict[str, Any]]:
    """Pick the most relevant organization to route a question to.

    Prefers an org already cited in the retrieved sources; otherwise matches by
    topic bucket and (loosely) city.
    """
    orgs = database.list_organizations()
    if not orgs:
        return None
    # 1) org already surfaced in retrieval
    for s in (retrieved_sources or []):
        if s.get("_is_org"):
            org = database.get_organization(s.get("_org_id"))
            if org:
                return org
    # 2) topic bucket -> org type
    bucket = classify_topic(topic)
    type_pref = {
        "education": "university",
        "labor": "employer",
        "health": "employer",
        "immigration": "support",
        "daily_life": "support",
    }.get(bucket)
    candidates = [o for o in orgs if o["org_type"] == type_pref] or orgs
    if city:
        city_l = city.lower()
        city_match = [o for o in candidates if city_l in (o.get("city", "") or "").lower()]
        if city_match:
            candidates = city_match
    return candidates[0]


def requester_label(profile: Optional[Dict[str, Any]]) -> str:
    """Build a coarse, PII-free requester label from the profile."""
    if not profile:
        return "Resident (anonymous)"
    parts = ["Resident"]
    if profile.get("resident_type"):
        parts.append(str(profile["resident_type"]))
    if profile.get("city"):
        parts.append(str(profile["city"]))
    return " · ".join(parts)


# ---------------------------------------------------------------------------
# Trends (privacy-protected aggregates)
# ---------------------------------------------------------------------------
def trends(org_city: Optional[str] = None) -> Dict[str, Any]:
    """Aggregate anonymized question logs. No raw question text or PII is stored
    or returned — only topic/city/language counts and recent volume."""
    rows = database.list_question_log()
    total = len(rows)
    by_topic = Counter(r["topic"] for r in rows if r.get("topic"))
    by_city = Counter(r["city"] for r in rows if r.get("city"))
    by_lang = Counter(r["language"] for r in rows if r.get("language"))

    # Volume over the last 14 days.
    today = datetime.utcnow().date()
    buckets = {(today - timedelta(days=i)).isoformat(): 0 for i in range(13, -1, -1)}
    for r in rows:
        try:
            d = datetime.fromisoformat(r["created_at"]).date().isoformat()
        except (ValueError, TypeError):
            continue
        if d in buckets:
            buckets[d] += 1

    return {
        "total": total,
        "by_topic": by_topic.most_common(),
        "by_city": by_city.most_common(),
        "by_language": by_lang.most_common(),
        "volume_by_day": buckets,
    }
