"""Trusted Services — the curated directory of official sources, plus a simple
language-assistance tool that prepares Korean messages/scripts with translations."""
from __future__ import annotations

import streamlit as st

from korealife import ai, config, knowledge, ui
from korealife.i18n import t

st.set_page_config(page_title="Trusted Services · KOREA-LIFE", page_icon="🏛️", layout="wide")
ui.inject_css()
ui.ensure_db()


def _translate_custom(text, profile):
    """Translate a custom message to Korean using Claude if available, else a safe wrapper."""
    if config.ai_enabled():
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=config.anthropic_api_key())
            msg = client.messages.create(
                model=config.anthropic_model(),
                max_tokens=600,
                system=(
                    "You are a translation helper for a foreign resident in Korea. Translate the user's "
                    "message into polite, natural Korean suitable for a public/government office, then give "
                    "an English back-translation. Return JSON: {\"ko\": string, \"en\": string}. Do not add "
                    "immigration, legal, or official advice."
                ),
                messages=[{"role": "user", "content": text}],
            )
            raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            import json

            start, end = raw.find("{"), raw.rfind("}")
            data = json.loads(raw[start : end + 1])
            data["mode"] = "live"
            return data
        except Exception:
            pass
    # Fallback: wrap the message in a polite Korean request to translate/read.
    return {
        "ko": f"안녕하세요. 외국인입니다. 아래 내용을 전달하고 싶습니다:\n\n[{text}]\n\n도와주시면 감사하겠습니다.",
        "en": text,
        "mode": "fallback",
    }


profile = ui.sidebar_status()

if not profile:
    st.warning("Please complete onboarding on the Home page first.")
    st.stop()

lang = profile.get("language", "en")
ui.page_header("Trusted Services", t("trusted_services", lang), "Official sources only — verify specifics directly with each.")

st.caption(knowledge.disclaimer())

tab_dir, tab_lang = st.tabs(["📒 Official directory", "🗣 Language assistance"])

# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------
with tab_dir:
    sources = knowledge.all_sources()
    topics = sorted({tp for s in sources for tp in s.get("topic", [])})
    chosen = st.multiselect("Filter by topic", topics)
    for s in sources:
        if chosen and not (set(chosen) & set(s.get("topic", []))):
            continue
        ui.source_citation(s)
    st.info(
        "These are navigation records pointing to official sources. They do not contain "
        "visa rules, eligibility, fees, or legal deadlines — confirm those on each official "
        "site or helpline. For urgent or case-specific immigration questions, call **1345**."
    )

# ---------------------------------------------------------------------------
# Language assistance
# ---------------------------------------------------------------------------
with tab_lang:
    st.markdown("Prepare a short **Korean message or script** you can show or say at an office, "
                "with a translation back into your language.")
    st.markdown(ui.mode_badge(), unsafe_allow_html=True)

    purpose = st.selectbox(
        "What do you need to communicate?",
        [
            "Ask for help in English/with an interpreter",
            "Ask about an immigration/residence matter",
            "Ask about a health insurance bill",
            "Ask about a work/labor issue",
            "Reschedule or ask about an appointment",
            "Custom message",
        ],
    )
    custom = ""
    if purpose == "Custom message":
        custom = st.text_area("Write your message in your own language", height=90)

    # Curated, safe phrase bank (no external claims). Always available offline.
    PHRASES = {
        "Ask for help in English/with an interpreter": {
            "ko": "안녕하세요. 외국인입니다. 영어로 안내해 주시거나 통역이 가능할까요?",
            "en": "Hello. I am a foreign resident. Could you assist me in English, or is an interpreter available?",
        },
        "Ask about an immigration/residence matter": {
            "ko": "안녕하세요. 체류(비자) 관련 문의가 있어서 왔습니다. 어떤 서류가 필요한지 확인하고 싶습니다.",
            "en": "Hello. I have a question about my stay (visa). I would like to confirm which documents are needed.",
        },
        "Ask about a health insurance bill": {
            "ko": "안녕하세요. 건강보험 고지서에 대해 문의하고 싶습니다. 납부 금액과 납부일을 확인할 수 있을까요?",
            "en": "Hello. I would like to ask about my health insurance bill. Can I confirm the amount and the payment date?",
        },
        "Ask about a work/labor issue": {
            "ko": "안녕하세요. 근로 조건에 대해 상담하고 싶습니다. 통역 지원이 가능한지 궁금합니다.",
            "en": "Hello. I would like to get advice about my working conditions. I am wondering if interpretation support is available.",
        },
        "Reschedule or ask about an appointment": {
            "ko": "안녕하세요. 예약을 변경하거나 확인하고 싶습니다. 도와주실 수 있나요?",
            "en": "Hello. I would like to change or confirm my appointment. Could you help me?",
        },
    }

    if st.button("Prepare Korean script", type="primary"):
        if purpose == "Custom message":
            if not custom.strip():
                st.error("Please write your message first.")
            else:
                result = _translate_custom(custom, profile)
                st.markdown("**🇰🇷 Korean**")
                st.code(result["ko"], language=None)
                st.markdown("**↩ Back-translation**")
                st.write(result["en"])
                if result.get("mode") == "fallback":
                    st.caption("Offline mode: showing your text with a Korean request wrapper. "
                               "Add an ANTHROPIC_API_KEY for full translation.")
        else:
            phrase = PHRASES.get(purpose, {})
            st.markdown("**🇰🇷 Korean (show or read aloud)**")
            st.code(phrase.get("ko", ""), language=None)
            st.markdown("**Meaning**")
            st.write(phrase.get("en", ""))
            st.caption("Curated phrase — safe to use at any public office. Interpretation via 1345 (immigration) "
                       "or local call centers is available for many languages.")
