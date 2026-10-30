"""System-written report text in the claim's language.

Clear Context has no language detection yet. Turkish-specific letters are a narrow
heuristic for choosing Turkish system text; any other claim gets English. Model-written
explanations are unaffected.
"""

import re

TURKISH_LETTERS = re.compile("[çğıöşüÇĞİÖŞÜ]")

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
    return "tr" if TURKISH_LETTERS.search(claim) else "en"


def report_text(key: str, claim: str, **values) -> str:
    return MESSAGES[key][claim_language(claim)].format(**values)
