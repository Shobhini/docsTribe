from typing import List
from app.extractors.base import extract_sentences

FOLLOWUP_KEYWORDS = [
    "follow up", "follow-up", "followup", "revisit", "review in",
    "come back", "return in", "next appointment", "consult",
    "refer to", "referral", "see specialist", "appointment in",
]


def extract_followups(text: str) -> List[str]:
    return extract_sentences(text, FOLLOWUP_KEYWORDS)
