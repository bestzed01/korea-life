"""Retrieval over the curated knowledge base.

Loads the hand-curated JSON of official sources and provides simple keyword +
geography scoring so the AI layer (and the fallback) only ever reason over
records that were actually retrieved. No external calls — the knowledge base is
local and version-controlled.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

from . import config

_STOPWORDS = {
    "the", "a", "an", "to", "of", "and", "or", "for", "in", "on", "my", "i",
    "is", "are", "do", "how", "what", "where", "who", "can", "with", "about",
    "if", "it", "me", "need", "when", "which", "there", "any", "get", "have",
    "korea", "korean", "south",
}

# English topic hints: expand a query toward the English terms used in sources.
_TOPIC_HINTS = {
    "immigration": ["visa", "immigration", "stay", "extend", "extension", "residence", "card", "arc", "reentry", "appointment", "office"],
    "health": ["health", "insurance", "nhis", "premium", "medical", "hospital", "clinic", "coverage"],
    "labor": ["work", "job", "labor", "labour", "employer", "wage", "salary", "overtime", "contract", "fired", "dismissal"],
    "civil": ["certificate", "document", "government24", "registration", "civil", "address"],
    "seoul": ["seoul", "dasan", "global center", "settle", "settling", "housing", "community"],
}

# Multilingual triggers so a question asked in Russian, Korean, or Uzbek maps
# onto the same English topic hints. Entries are lowercase STEMS matched as
# substrings of the query, which tolerates inflected forms (e.g. "визу",
# "продлить" -> stems "виз", "продл"). The knowledge base content is English,
# so matching a trigger expands the query with that topic's English terms before
# scoring against the source text.
_MULTILINGUAL_TRIGGERS = {
    "immigration": [
        # ru
        "виз", "иммиграц", "жительств", "продл", "пребыван", "регистрац", "записать", "запис", "офис", "удостоверен", "карт",
        # uz
        "viza", "immigratsiya", "yashash", "uzaytir", "ro'yxat", "muddat", "idora",
        # ko
        "비자", "체류", "연장", "외국인등록", "출입국", "예약", "거주",
    ],
    "health": [
        "страхов", "медицин", "больниц", "взнос", "健康", "здоровь",  # ru/misc
        "sug'urta", "sugurta", "tibbiy", "kasalxona",                 # uz
        "건강보험", "보험", "병원", "의료", "보험료",                   # ko
    ],
    "labor": [
        "работ", "труд", "зарплат", "зарплата", "контракт", "договор", "увольн", "сверхуроч",  # ru
        "ish", "mehnat", "maosh", "shartnoma", "ishchi",                                        # uz
        "노동", "근로", "임금", "급여", "계약", "직장", "해고",                                   # ko
    ],
    "civil": [
        "справк", "документ", "свидетельств", "регистрац",  # ru
        "hujjat", "guvohnoma",                                # uz
        "증명", "서류", "민원", "발급",                        # ko
    ],
    "seoul": [
        "сеул", "сеуле",                 # ru
        "seul",                          # uz
        "서울",                           # ko
    ],
}


@lru_cache(maxsize=1)
def _load_raw() -> Dict[str, Any]:
    with open(config.KNOWLEDGE_BASE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def all_sources() -> List[Dict[str, Any]]:
    return list(_load_raw().get("sources", []))


def disclaimer() -> str:
    return _load_raw().get("meta", {}).get("disclaimer", "")


def get_source(source_id: str) -> Optional[Dict[str, Any]]:
    for src in all_sources():
        if src.get("id") == source_id:
            return src
    return None


def get_sources(source_ids: List[str]) -> List[Dict[str, Any]]:
    index = {s["id"]: s for s in all_sources()}
    return [index[sid] for sid in source_ids if sid in index]


def _tokenize(text: str) -> List[str]:
    tokens = re.findall(r"[a-zA-Z]+", (text or "").lower())
    return [tok for tok in tokens if tok not in _STOPWORDS and len(tok) > 1]


def _multilingual_expansion(query: str) -> set:
    """Return English topic-hint terms triggered by non-English (or English)
    query text. Lets Russian/Korean/Uzbek queries retrieve the English-language
    source records.

    Matching rules avoid false positives:
    - ASCII stems (Latin, e.g. Uzbek "ish") match a query word by PREFIX only,
      so "ish" matches "ishga" but not "gibberish" or "english".
    - Non-ASCII stems (Cyrillic/Hangul) match as substrings, tolerating
      inflected endings (e.g. "виз" in "визу").
    """
    lowered = (query or "").lower()
    word_tokens = re.findall(r"[^\W\d_]+", lowered, re.UNICODE)
    expansion: set = set()
    for area, stems in _MULTILINGUAL_TRIGGERS.items():
        hit = False
        for stem in stems:
            if stem.isascii():
                if any(tok.startswith(stem) for tok in word_tokens):
                    hit = True
                    break
            else:
                if stem in lowered:
                    hit = True
                    break
        if hit:
            expansion |= set(_TOPIC_HINTS.get(area, []))
    return expansion


def _source_terms(src: Dict[str, Any]) -> str:
    parts = [
        src.get("title", ""),
        src.get("issuer", ""),
        " ".join(src.get("topic", [])),
        src.get("verified_summary", ""),
        " ".join(src.get("excerpts", [])),
    ]
    return " ".join(parts).lower()


def retrieve(
    query: str,
    profile: Optional[Dict[str, Any]] = None,
    top_k: int = 3,
    extra_sources: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Score sources against the query and (optionally) the user's city.

    `extra_sources` lets callers add source-shaped records beyond the curated
    knowledge base — in particular organization-published resources from
    KOREA-LIFE Connect — so they can be scored and cited alongside official
    sources. They are matched and ranked by the same logic.

    Returns up to top_k sources sorted by relevance. If nothing scores above
    zero, returns an empty list so the caller can honestly say the knowledge
    base does not cover the question.
    """
    query_tokens = set(_tokenize(query))
    # Expand with English topic hints (for English queries)...
    expanded = set(query_tokens)
    for hint_terms in _TOPIC_HINTS.values():
        if query_tokens & set(hint_terms):
            expanded |= set(hint_terms)
    # ...and with multilingual triggers (for Russian/Korean/Uzbek queries).
    expanded |= _multilingual_expansion(query)

    # Terms used for topic-field direct hits include the expansion, so a
    # non-English query can still score topic matches.
    match_tokens = query_tokens | expanded

    city = ((profile or {}).get("city") or "").strip().lower()

    pool = all_sources() + list(extra_sources or [])
    scored: List[tuple] = []
    for src in pool:
        terms = _source_terms(src)
        term_tokens = set(_tokenize(terms))
        overlap = len(expanded & term_tokens)
        score = float(overlap)

        # Topic field direct hits weigh more.
        for topic in src.get("topic", []):
            if any(tok in topic.lower() for tok in match_tokens):
                score += 1.5

        # Geography boost / filter applies ONLY to sources that already have a
        # topical match, so an irrelevant query never retrieves a source just
        # because the user lives in that city.
        if score > 0:
            geo = (src.get("geography", "") or "").lower()
            if "seoul" in geo:
                if city and "seoul" in city:
                    score += 1.0
                elif city and "seoul" not in city:
                    score -= 1.0  # de-prioritize Seoul-only source for non-Seoul users

        if score > 0:
            scored.append((score, src))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [src for _, src in scored[:top_k]]


def build_evidence_block(sources: List[Dict[str, Any]]) -> str:
    """Format retrieved sources into a compact evidence block for the model."""
    if not sources:
        return "NO SOURCES RETRIEVED."
    lines = []
    for s in sources:
        lines.append(
            f"[{s['id']}] {s['title']} — issuer: {s['issuer']}; "
            f"geography: {s.get('geography','')}; url: {s['url']}\n"
            f"  topics: {', '.join(s.get('topic', []))}\n"
            f"  verified_summary: {s.get('verified_summary','')}\n"
            f"  escalation_contact: {s.get('escalation_contact','')}\n"
            f"  last_checked: {s.get('last_checked','')}"
        )
    return "\n\n".join(lines)
