"""System-written report text in the input's language.

Research detects the input language once (services/language.py) and sets it for the
investigation. Without it, Turkish-specific letters in the claim are a narrow fallback;
any language without messages here gets English. Model-written explanations are unaffected.
"""

import re
from contextlib import contextmanager
from contextvars import ContextVar

TURKISH_LETTERS = re.compile("[çğıöşüÇĞİÖŞÜ]")
# Set per investigation; async tasks started inside the research run inherit it.
REPORT_LANGUAGE: ContextVar[str | None] = ContextVar("report_language", default=None)

MESSAGES = {
    "no_evidence": {
        "en": "No source passage was selected for this detail, so no model assessment was made.",
        "tr": "Bu detay için kaynak pasajı seçilmedi; model değerlendirmesi yapılmadı.",
    },
    "assessment_failed": {
        "en": "Evidence assessment did not complete ({status}); this detail was not evaluated.",
        "tr": "Kanıt değerlendirmesi tamamlanmadı ({status}); bu detay değerlendirilmedi.",
    },
    "needs_context": {
        "en": "Not researched: the claim lacks context this detail depends on.",
        "tr": "Araştırılmadı: iddiada bu detayın dayandığı bağlam eksik.",
    },
    "budget_deferred": {
        "en": "Not researched within this investigation's search budget.",
        "tr": "Bu araştırmanın arama bütçesi içinde araştırılmadı.",
    },
    "claim_wide_unresolved": {
        "en": "Claim-wide coverage is not established; review each detail below.",
        "tr": "İddianın tamamı için kapsam doğrulanmadı; aşağıdaki detayları tek tek inceleyin.",
    },
}


def claim_language(claim: str) -> str:
    detected = REPORT_LANGUAGE.get()
    if detected:
        return detected if detected in MESSAGES["no_evidence"] else "en"
    return "tr" if TURKISH_LETTERS.search(claim) else "en"


@contextmanager
def report_language(code: str | None):
    token = REPORT_LANGUAGE.set(code)
    try:
        yield
    finally:
        REPORT_LANGUAGE.reset(token)


def report_text(key: str, claim: str, **values) -> str:
    return MESSAGES[key][claim_language(claim)].format(**values)
