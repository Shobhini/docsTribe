from typing import List
from app.extractors.base import extract_sentences

LAB_KEYWORDS = [
    "cbc", "blood test", "hemoglobin", "glucose", "lipid panel",
    "thyroid", "tsh", "hba1c", "urine test", "creatinine",
    "liver function", "lft", "rft", "complete blood count",
    "blood sugar", "platelet", "wbc", "rbc",
]


def extract_lab_tests(text: str) -> List[str]:
    return extract_sentences(text, LAB_KEYWORDS)
