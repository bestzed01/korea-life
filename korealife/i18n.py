"""Minimal UI translation dictionary for the four supported languages.

Only a small set of recurring UI strings is translated. The app is designed to
work fully in English and uses these for lightweight localization of headings
and labels. Missing keys fall back to English.
"""
from __future__ import annotations

LANGUAGES = {
    "en": "English",
    "ru": "Русский (Russian)",
    "uz": "Oʻzbekcha (Uzbek)",
    "ko": "한국어 (Korean)",
}

_STRINGS = {
    "app_tagline": {
        "en": "Your multilingual guide to official life in South Korea",
        "ru": "Ваш многоязычный помощник по официальной жизни в Южной Корее",
        "uz": "Janubiy Koreyada rasmiy hayot boʻyicha koʻp tilli yordamchingiz",
        "ko": "대한민국 생활을 위한 다국어 안내 도우미",
    },
    "home": {"en": "Home", "ru": "Главная", "uz": "Bosh sahifa", "ko": "홈"},
    "copilot": {"en": "AI Copilot", "ru": "ИИ-помощник", "uz": "AI yordamchi", "ko": "AI 코파일럿"},
    "life_plan": {"en": "My Life Plan", "ru": "Мой план", "uz": "Mening rejam", "ko": "내 라이프 플랜"},
    "life_manager": {"en": "Life Manager", "ru": "Менеджер жизни", "uz": "Hayot menejeri", "ko": "라이프 매니저"},
    "trusted_services": {"en": "Trusted Services", "ru": "Проверенные службы", "uz": "Ishonchli xizmatlar", "ko": "공식 서비스"},
    "today": {"en": "Today", "ru": "Сегодня", "uz": "Bugun", "ko": "오늘"},
    "upcoming": {"en": "Upcoming", "ru": "Предстоящие", "uz": "Kelgusi", "ko": "예정"},
    "overdue": {"en": "Overdue", "ru": "Просроченные", "uz": "Muddati oʻtgan", "ko": "기한 초과"},
    "completed": {"en": "Completed", "ru": "Завершённые", "uz": "Bajarilgan", "ko": "완료"},
    "ask_placeholder": {
        "en": "Ask about immigration, health insurance, labor, or daily life...",
        "ru": "Спросите об иммиграции, страховке, труде или повседневной жизни...",
        "uz": "Immigratsiya, sugʻurta, mehnat yoki kundalik hayot haqida soʻrang...",
        "ko": "출입국, 건강보험, 노동, 생활 등에 대해 질문하세요...",
    },
}


def t(key: str, lang: str = "en") -> str:
    """Translate a UI key, falling back to English then to the key itself."""
    entry = _STRINGS.get(key)
    if not entry:
        return key
    return entry.get(lang) or entry.get("en") or key


def language_name(code: str) -> str:
    return LANGUAGES.get(code, code)
