"""Core logic tests for KOREA-LIFE. Run with:  python -m tests.test_core
Uses a temporary SQLite DB so it never touches real data.
"""
import os
import sys
import tempfile
from datetime import date, timedelta

# Use an isolated DB before importing the package modules that read config.
_TMP = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_TMP.close()
os.environ["KOREA_LIFE_DB"] = _TMP.name
# Ensure no live API calls during tests.
os.environ.pop("ANTHROPIC_API_KEY", None)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from korealife import ai, connect, database, extract, knowledge, reminders  # noqa: E402

PASS = 0
FAIL = 0


def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")


def test_database_and_recurrence():
    print("database + recurrence")
    database.init_db()
    database.delete_all_reminders()
    rid = database.add_reminder(
        title="NHIS premium", category="health_insurance",
        due_date=date.today().isoformat(), amount=120000, recurrence="monthly",
        reminder_offsets=[7, 1],
    )
    check("reminder created", rid > 0)
    r = database.get_reminder(rid)
    check("fields persisted", r["title"] == "NHIS premium" and r["amount"] == 120000)
    check("offsets stored as list", r["reminder_offsets"] == [7, 1])

    new_id = reminders.complete_reminder(rid)
    check("recurring completion creates next occurrence", new_id is not None and new_id != rid)
    old = database.get_reminder(rid)
    check("original marked completed", old["status"] == "completed")
    nxt = database.get_reminder(new_id)
    expected = reminders.next_due_date(date.today().isoformat(), "monthly")
    check("next due date is one month later", nxt["due_date"] == expected)


def test_status_and_offsets():
    print("status computation")
    today = date.today()
    overdue = {"due_date": (today - timedelta(days=2)).isoformat(), "status": "upcoming", "reminder_offsets": [7]}
    due_today = {"due_date": today.isoformat(), "status": "upcoming", "reminder_offsets": [7]}
    soon = {"due_date": (today + timedelta(days=3)).isoformat(), "status": "upcoming", "reminder_offsets": [7]}
    far = {"due_date": (today + timedelta(days=40)).isoformat(), "status": "upcoming", "reminder_offsets": [7]}
    check("overdue detected", reminders.compute_display_status(overdue) == reminders.STATUS_OVERDUE)
    check("today detected", reminders.compute_display_status(due_today) == reminders.STATUS_TODAY)
    check("due soon detected", reminders.compute_display_status(soon) == reminders.STATUS_DUE_SOON)
    check("upcoming detected", reminders.compute_display_status(far) == reminders.STATUS_UPCOMING)

    snoozed = dict(overdue)
    snoozed["snoozed_until"] = (today + timedelta(days=5)).isoformat()
    check("snoozed treated as upcoming", reminders.compute_display_status(snoozed) == reminders.STATUS_UPCOMING)


def test_document_expiry_offsets():
    print("document expiry multi-offset")
    offs = reminders.default_offsets_for("residence_card")
    check("residence card has 60/30/7 offsets", offs == [60, 30, 7])
    today = date.today()
    r = {"due_date": (today + timedelta(days=30)).isoformat(), "status": "upcoming", "reminder_offsets": [60, 30, 7]}
    triggers = reminders.active_offset_triggers(r)
    check("30-day and 60-day offsets active at 30 days out", 30 in triggers and 60 in triggers and 7 not in triggers)


def test_extraction():
    print("notice extraction")
    text = "National Health Insurance. Amount: KRW 128,500. Payment due date: 2026-12-10. Issued 2026.11.20."
    cand = extract.extract_candidates(text)
    check("date extracted", "2026-12-10" in cand["dates"])
    check("amount extracted", 128500 in cand["amounts"])
    check("suggests a future due date", cand["suggested_due_date"] in cand["dates"])


def test_knowledge_retrieval():
    print("knowledge retrieval")
    srcs = knowledge.retrieve("How do I extend my visa and book an immigration appointment?")
    ids = [s["id"] for s in srcs]
    check("immigration query retrieves HiKorea/1345", "HIKOREA" in ids or "MOJ1345" in ids)
    health = knowledge.retrieve("question about my health insurance premium bill")
    check("health query retrieves NHIS", "NHIS_FOREIGN" in [s["id"] for s in health])
    none = knowledge.retrieve("asdfqwer zxcvbnm nonsense tokens")
    check("irrelevant query retrieves nothing", none == [])

    # Multilingual retrieval (regression): non-Latin queries must retrieve.
    ru = [s["id"] for s in knowledge.retrieve("Как продлить визу", profile={"city": "Seoul"})]
    check("Russian immigration query retrieves immigration sources", "HIKOREA" in ru or "MOJ1345" in ru)
    ko = [s["id"] for s in knowledge.retrieve("건강보험료 문의", profile={"city": "Seoul"})]
    check("Korean health query retrieves NHIS", "NHIS_FOREIGN" in ko)
    uz = [s["id"] for s in knowledge.retrieve("mehnat shartnomasi haqida", profile={"city": "Seoul"})]
    check("Uzbek labor query retrieves MOEL", "MOEL1350" in uz)
    # Latin false-positive guard: short stem "ish" must not trigger labor.
    guard = knowledge.retrieve("finish my dish")
    check("'ish' substring does not cause false retrieval", guard == [])


def test_ai_fallback():
    print("AI fallback (offline, deterministic)")
    profile = {"language": "en", "resident_type": "employee", "city": "Seoul", "is_demo": True}
    res = ai.ask("How do I extend my stay in Korea?", profile=profile)
    check("runs in fallback mode", res["mode"] == "fallback")
    check("cites only retrieved source ids", all(sid in {s["id"] for s in res["_retrieved_sources"]} for sid in res["source_ids"]))
    check("high-stakes flagged for verification", res["needs_official_verification"] is True)
    check("has action steps", len(res["action_steps"]) >= 1)

    empty = ai.ask("random unrelated gibberish wqxyz", profile=profile)
    check("no-source question yields empty citations", empty["source_ids"] == [])
    check("no-source question still flags verification/escalation", bool(empty["escalation_contact"]))

    # Russian question must produce a grounded answer (not the no-source fallback).
    ru_profile = {"language": "ru", "resident_type": "employee", "city": "Seoul"}
    ru_res = ai.ask("Как продлить визу и записаться в иммиграционную службу?", profile=ru_profile)
    check("Russian question retrieves and cites sources", len(ru_res["source_ids"]) > 0)
    check("Russian answer contains Cyrillic text", any("Ѐ" <= ch <= "ӿ" for ch in ru_res["answer"]))


def test_connect():
    print("KOREA-LIFE Connect (two-sided platform)")
    database.init_db()
    connect.seed_demo(force=True)
    check("demo organizations seeded", database.count_organizations() >= 3)
    check("published resources exist", len(database.list_org_resources(only_published=True)) >= 5)
    check("demo inquiries seeded", len(database.list_inquiries()) >= 1)

    # Org resources must surface in the assistant's retrieval and be citable.
    prof = {"language": "en", "resident_type": "student", "city": "Seoul", "is_demo": True}
    res = ai.ask("How do I get an enrollment certificate for my visa and bank?", profile=prof)
    surfaced = [s for s in res["_retrieved_sources"] if s.get("_is_org")]
    check("organization resource surfaced to assistant", len(surfaced) >= 1)
    check("org source ids are citable (valid)", all(s in {x["id"] for x in res["_retrieved_sources"]} for s in res["source_ids"]))
    check("both official and org sources can co-retrieve", any(not s.get("_is_org") for s in res["_retrieved_sources"]))

    # Routing picks an organization.
    org = connect.suggest_org_for("enrollment certificate", city="Seoul", retrieved_sources=res["_retrieved_sources"])
    check("question routes to an organization", org is not None)

    # Inquiry round-trip, PII-free label.
    before = len(database.list_inquiries(org_id=org["id"]))
    database.add_inquiry(org_id=org["id"], message="Can you help with my transcript?",
                         requester_label=connect.requester_label(prof), topic="education", source="copilot")
    after = len(database.list_inquiries(org_id=org["id"]))
    check("inquiry created for org", after == before + 1)
    label = connect.requester_label(prof)
    check("requester label carries no name/PII", "Resident" in label and "@" not in label)

    # Trends are anonymized aggregates.
    tr = connect.trends()
    check("trends aggregate has topic counts", len(tr["by_topic"]) >= 1)
    check("trend logging has no raw question text", all(set(r.keys()) >= {"topic", "city", "language"} and "message" not in r for r in database.list_question_log()))


def main():
    print("\n=== KOREA-LIFE core tests ===\n")
    test_database_and_recurrence()
    test_status_and_offsets()
    test_document_expiry_offsets()
    test_extraction()
    test_knowledge_retrieval()
    test_ai_fallback()
    test_connect()
    print(f"\n=== {PASS} passed, {FAIL} failed ===")
    try:
        os.unlink(_TMP.name)
    except OSError:
        pass
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
