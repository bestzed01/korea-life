"""The AI layer.

Given a user question and profile, it:
1. retrieves relevant sources from the curated knowledge base, and
2. asks Claude to answer using ONLY that retrieved evidence, returning a strict
   JSON structure.

If no API key is configured (or the API call fails), a deterministic fallback
produces a structured response grounded in the same retrieved records, so the
app remains fully usable offline as a demo. Fallback output is clearly labeled.

The response schema (both live and fallback) has keys:
  answer, applicability, clarifying_questions, action_steps, source_ids,
  uncertainty, escalation_contact, korean_script, needs_official_verification,
  mode
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from . import config, knowledge

# Topics where we always flag for official verification.
HIGH_STAKES_TOPICS = {"immigration", "visa", "legal", "labor", "healthcare", "health", "financial", "tax"}

HIGH_STAKES_KEYWORDS = [
    "visa", "immigration", "deport", "overstay", "extend", "extension", "residence card",
    "arc", "legal", "lawyer", "court", "fine", "penalty", "labor", "labour", "wage",
    "salary", "fired", "dismiss", "contract", "insurance", "premium", "medical", "hospital",
    "tax", "refund", "money", "bank", "loan", "deadline", "expire", "expiry", "eligib",
]

SYSTEM_PROMPT = """You are KOREA-LIFE, a careful multilingual assistant for foreign residents of South Korea.

ABSOLUTE RULES:
- Use ONLY the information in the RETRIEVED SOURCES block provided in the user message. Do not use outside knowledge about Korean immigration, visa, labor, healthcare, tax, or legal rules.
- NEVER invent or state specific visa rules, eligibility criteria, requirements, fees, amounts, processing times, or legal deadlines. The retrieved sources are navigation aids with high-level summaries only; they do not contain these specifics.
- If the retrieved sources do not support a direct answer, say so plainly and direct the user to the relevant official contact. Do not guess.
- Cite ONLY source IDs that actually appear in the RETRIEVED SOURCES block. If none were retrieved, use an empty source_ids list.
- Some sources are organization-published (their issuer is marked "organization (demo)"). You may relay that organization's own stated procedure, FAQ, or requirement and attribute it to them by name. Even so, do not state government visa, immigration, or legal rules or deadlines that are not present in the sources, and keep directing high-stakes matters to the official body.
- For any immigration, visa, legal, labor, healthcare, or financial/tax question, set needs_official_verification to true and remind the user to confirm with the official source.
- Be concise, practical, and respectful. Write the main answer in the user's preferred language when possible.

OUTPUT: Return ONLY a single JSON object, no prose before or after, with exactly these keys:
{
  "answer": string,                       // plain-language answer grounded in sources; in the user's language
  "applicability": string,                // how this applies to the user's stated profile, with caveats; "" if unknown
  "clarifying_questions": [string],       // questions you need answered to help further; [] if none
  "action_steps": [                       // concrete next steps the user can take
    {"title": string, "detail": string, "suggested_category": string, "suggested_offset_days": [int]}
  ],
  "source_ids": [string],                 // only IDs from the retrieved block
  "uncertainty": "low" | "medium" | "high",
  "escalation_contact": string,           // the best official contact to verify/act, drawn from sources
  "korean_script": string,                // a short Korean phrase/script the user could say or show at an office, or ""
  "needs_official_verification": boolean
}
Keep action_steps practical and tied to official channels. suggested_category must be one of:
health_insurance, residence_card, passport, visa, rent, utilities, tuition, employment_contract, subscription, appointment, tax, task, other.
"""


def is_high_stakes(query: str, sources: List[Dict[str, Any]]) -> bool:
    q = (query or "").lower()
    if any(kw in q for kw in HIGH_STAKES_KEYWORDS):
        return True
    for s in sources:
        if set(t.lower() for t in s.get("topic", [])) & HIGH_STAKES_TOPICS:
            return True
    return False


def _profile_summary(profile: Optional[Dict[str, Any]]) -> str:
    if not profile:
        return "No profile provided."
    parts = [
        f"preferred_language={profile.get('language','en')}",
        f"resident_type={profile.get('resident_type','unknown')}",
        f"city={profile.get('city','unknown')}",
    ]
    if profile.get("residence_category"):
        parts.append(f"residence_category={profile.get('residence_category')}")
    if profile.get("is_demo"):
        parts.append("NOTE=this is SYNTHETIC demo profile data")
    return "; ".join(parts)


def ask(query: str, profile: Optional[Dict[str, Any]] = None, top_k: int = 4, log_trend: bool = True) -> Dict[str, Any]:
    """Main entry point. Retrieves sources and returns a structured response dict.

    Organization-published resources from KOREA-LIFE Connect are merged into the
    retrieval pool so the assistant can cite an organization's own verified
    procedure when relevant. The question is also logged as an anonymized topic
    bucket (no raw text, no PII) to power the Connect trends dashboard.
    """
    query = (query or "").strip()

    # Pull in organization-published resources as additional candidate sources.
    try:
        from . import connect

        extra = connect.published_resources_as_sources()
    except Exception:
        connect = None
        extra = []

    sources = knowledge.retrieve(query, profile=profile, top_k=top_k, extra_sources=extra)
    high_stakes = is_high_stakes(query, sources)

    # Anonymized trend logging (topic bucket + coarse city + language only).
    if log_trend and connect is not None and query:
        try:
            database_city = (profile or {}).get("city", "")
            connect.database.log_question(
                topic=connect.classify_topic(query),
                city=database_city,
                language=(profile or {}).get("language", ""),
                is_demo=bool((profile or {}).get("is_demo")),
            )
        except Exception:
            pass

    if config.ai_enabled():
        try:
            result = _ask_claude(query, profile, sources)
            result["mode"] = "live"
        except Exception as exc:  # fall back gracefully on any API/parse error
            result = _fallback_answer(query, profile, sources)
            result["mode"] = "fallback"
            detail = str(exc).strip().replace("\n", " ")
            if len(detail) > 180:
                detail = detail[:180] + "…"
            result["_fallback_reason"] = (
                f"AI call failed ({type(exc).__name__}): {detail} — showing offline demo answer."
            )
    else:
        result = _fallback_answer(query, profile, sources)
        result["mode"] = "fallback"

    # Enforce safety invariants regardless of mode.
    valid_ids = {s["id"] for s in sources}
    result["source_ids"] = [sid for sid in result.get("source_ids", []) if sid in valid_ids]
    if high_stakes:
        result["needs_official_verification"] = True
    result.setdefault("needs_official_verification", high_stakes)
    result["_retrieved_sources"] = sources
    result["_high_stakes"] = high_stakes
    return result


def _ask_claude(query: str, profile: Optional[Dict[str, Any]], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    import anthropic

    client = anthropic.Anthropic(api_key=config.anthropic_api_key())
    evidence = knowledge.build_evidence_block(sources)
    user_msg = (
        f"USER PROFILE: {_profile_summary(profile)}\n\n"
        f"RETRIEVED SOURCES (the ONLY evidence you may use):\n{evidence}\n\n"
        f"USER QUESTION: {query}\n\n"
        f"Respond with the JSON object described in the system instructions. "
        f"The answer field should be written in the user's preferred language."
    )
    # Try the configured model first, then widely-available fallbacks if the
    # configured one returns "model not found" (404). Other errors (auth,
    # overloaded, etc.) are raised immediately — retrying other models won't help.
    not_found = getattr(anthropic, "NotFoundError", None)
    last_not_found: Optional[Exception] = None
    message = None
    for model_name in config.candidate_models():
        try:
            message = client.messages.create(
                model=model_name,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
            )
            break
        except Exception as exc:  # noqa: BLE001
            is_not_found = (not_found is not None and isinstance(exc, not_found)) or "not_found" in str(exc).lower()
            if is_not_found:
                last_not_found = exc
                continue
            raise
    if message is None:
        raise last_not_found or RuntimeError("No usable Claude model found for this API key.")

    text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
    return _parse_json_response(text, sources)


def _parse_json_response(text: str, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    text = (text or "").strip()
    # Strip code fences if present.
    if text.startswith("```"):
        text = text.split("```", 2)[1] if text.count("```") >= 2 else text.strip("`")
        if text.lstrip().startswith("json"):
            text = text.lstrip()[4:]
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    data = json.loads(text[start : end + 1])

    # Normalize / default fields.
    data.setdefault("answer", "")
    data.setdefault("applicability", "")
    data.setdefault("clarifying_questions", [])
    data.setdefault("action_steps", [])
    data.setdefault("source_ids", [])
    data.setdefault("uncertainty", "medium")
    data.setdefault("escalation_contact", "")
    data.setdefault("korean_script", "")
    data.setdefault("needs_official_verification", False)
    # Ensure action_steps shape.
    normalized_steps = []
    for step in data.get("action_steps", []):
        if isinstance(step, str):
            step = {"title": step, "detail": "", "suggested_category": "task", "suggested_offset_days": [3]}
        step.setdefault("title", "")
        step.setdefault("detail", "")
        step.setdefault("suggested_category", "task")
        step.setdefault("suggested_offset_days", [3])
        normalized_steps.append(step)
    data["action_steps"] = normalized_steps
    return data


# ---------------------------------------------------------------------------
# Deterministic fallback (no API key / API failure)
# ---------------------------------------------------------------------------
def _fallback_answer(query: str, profile: Optional[Dict[str, Any]], sources: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a structured answer purely from retrieved records. Honest and safe:
    it summarizes what the official sources cover and points to official contacts,
    never asserting specific rules."""
    lang = (profile or {}).get("language", "en")

    if not sources:
        msg = {
            "en": "I don't have an official source in this app's knowledge base that covers your question, so I can't answer it reliably. Please contact an official channel: the Immigration Contact Center 1345 for immigration matters, or the relevant ministry helpline, for an authoritative answer.",
            "ru": "В базе знаний этого приложения нет официального источника по вашему вопросу, поэтому я не могу дать надёжный ответ. Обратитесь в официальный канал: контакт-центр иммиграции 1345 по вопросам иммиграции или в соответствующую горячую линию министерства.",
            "uz": "Ushbu ilova bilimlar bazasida savolingizni qamrab oladigan rasmiy manba yoʻq, shuning uchun ishonchli javob bera olmayman. Rasmiy kanalga murojaat qiling: immigratsiya masalalari boʻyicha 1345 immigratsiya aloqa markazi yoki tegishli vazirlik yordam liniyasi.",
            "ko": "이 앱의 지식베이스에 귀하의 질문을 다루는 공식 출처가 없어 정확히 답변드릴 수 없습니다. 출입국 민원은 1345 외국인종합안내센터 등 공식 창구에 문의하세요.",
        }
        return {
            "answer": msg.get(lang, msg["en"]),
            "applicability": "",
            "clarifying_questions": [],
            "action_steps": [],
            "source_ids": [],
            "uncertainty": "high",
            "escalation_contact": "Immigration Contact Center 1345 (within Korea)",
            "korean_script": "",
            "needs_official_verification": True,
            "_fallback_note": "Offline demo answer: no matching source found.",
        }

    primary = sources[0]
    # Compose a grounded, source-citing answer.
    summaries = " ".join(f"{s['title']} ({s['issuer']}): {s['verified_summary']}" for s in sources)
    header = {
        "en": "Here is what the official sources in this app cover for your question. This is a navigation guide, not legal or official advice — confirm specifics on the official site or helpline.",
        "ru": "Вот что по вашему вопросу покрывают официальные источники в приложении. Это навигационная подсказка, а не юридическая консультация — уточняйте детали на официальном сайте или горячей линии.",
        "uz": "Savolingiz boʻyicha ushbu ilovadagi rasmiy manbalar quyidagilarni qamrab oladi. Bu yoʻl koʻrsatuvchi maʼlumot, yuridik maslahat emas — tafsilotlarni rasmiy saytdan yoki yordam liniyasidan tasdiqlang.",
        "ko": "귀하의 질문과 관련해 이 앱의 공식 출처가 다루는 내용입니다. 법률·공식 자문이 아닌 안내이므로 구체적인 사항은 공식 사이트나 안내센터에서 확인하세요.",
    }
    answer = f"{header.get(lang, header['en'])}\n\n{summaries}"

    escalation = primary.get("escalation_contact", "Immigration Contact Center 1345 (within Korea)")

    action_steps = [
        {
            "title": f"Open the official page: {primary['title']}",
            "detail": f"Visit {primary['url']} to read the authoritative, up-to-date information from {primary['issuer']}.",
            "suggested_category": "task",
            "suggested_offset_days": [3],
        },
        {
            "title": f"Contact {escalation} to confirm your specific case",
            "detail": "Your exact situation depends on your status and circumstances. Ask the official contact to confirm any requirement, amount, or deadline before you act.",
            "suggested_category": "appointment",
            "suggested_offset_days": [3, 1],
        },
    ]

    korean_script = {
        "immigration": "안녕하세요. 외국인 등록/체류 관련 문의를 하고 싶습니다. 영어(또는 통역) 가능할까요?",
        "health": "안녕하세요. 건강보험 관련 문의가 있습니다. 도와주실 수 있나요?",
        "labor": "안녕하세요. 근로 조건에 대해 상담하고 싶습니다. 통역이 가능할까요?",
    }
    topics = set(t.lower() for s in sources for t in s.get("topic", []))
    kscript = ""
    if topics & {"immigration", "visa", "residence card"}:
        kscript = korean_script["immigration"]
    elif topics & {"health insurance", "healthcare"}:
        kscript = korean_script["health"]
    elif topics & {"labor", "employment"}:
        kscript = korean_script["labor"]

    clarifying = []
    if not (profile or {}).get("residence_category"):
        clarifying.append(
            {
                "en": "What is your residence/visa category? That changes which rules apply.",
                "ru": "Какая у вас категория пребывания/визы? От этого зависят применимые правила.",
                "uz": "Yashash/viza toifangiz qanday? Bu qaysi qoidalar amal qilishini belgilaydi.",
                "ko": "체류/비자 유형이 무엇인가요? 적용 규정이 달라집니다.",
            }.get(lang, "What is your residence/visa category?")
        )

    return {
        "answer": answer,
        "applicability": _applicability_note(profile, lang),
        "clarifying_questions": clarifying,
        "action_steps": action_steps,
        "source_ids": [s["id"] for s in sources],
        "uncertainty": "medium",
        "escalation_contact": escalation,
        "korean_script": kscript,
        "needs_official_verification": True,
        "_fallback_note": "This is a deterministic offline demo answer grounded in the retrieved official-source records. Enable an ANTHROPIC_API_KEY for AI-generated answers.",
    }


def _applicability_note(profile: Optional[Dict[str, Any]], lang: str) -> str:
    if not profile:
        return ""
    city = profile.get("city", "")
    rtype = profile.get("resident_type", "")
    base = {
        "en": f"Based on your profile (resident type: {rtype}, city: {city}). Seoul-specific services apply only if you live in Seoul; otherwise check your own local government's foreign-resident office.",
        "ru": f"На основе вашего профиля (тип: {rtype}, город: {city}). Услуги для Сеула применимы только если вы живёте в Сеуле.",
        "uz": f"Profilingizga asosan (toifa: {rtype}, shahar: {city}). Seulga xos xizmatlar faqat Seulda yashasangiz amal qiladi.",
        "ko": f"프로필 기준(유형: {rtype}, 도시: {city}). 서울 전용 서비스는 서울 거주자에게만 적용됩니다.",
    }
    if (profile or {}).get("is_demo"):
        note = {
            "en": " (Demo profile is synthetic.)",
            "ru": " (Демо-профиль синтетический.)",
            "uz": " (Demo profil sintetik.)",
            "ko": " (데모 프로필은 가상 데이터입니다.)",
        }.get(lang, " (Demo profile is synthetic.)")
        return base.get(lang, base["en"]) + note
    return base.get(lang, base["en"])
