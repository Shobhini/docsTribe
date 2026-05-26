from typing import List
from app.extractors.base import extract_sentences

RADIOLOGY_KEYWORDS = [
    "x-ray", "xray", "mri", "ct scan", "ultrasound", "sonography",
    "chest x-ray", "echocardiogram", "mammogram", "bone scan",
    "pet scan", "dexa scan", "doppler", "angiogram",
]


def extract_radiology(text: str) -> List[str]:
    return extract_sentences(text, RADIOLOGY_KEYWORDS)
