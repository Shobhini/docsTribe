import re
from typing import List


def extract_sentences(text: str, keywords: List[str]) -> List[str]:
    """
    Find all sentences in text that contain any of the given keywords.
    Returns deduplicated list of matching sentences.
    """
    # Split on newlines first, then on sentence-ending punctuation.
    # We split on newlines directly and on '.' only when followed by
    # whitespace + uppercase (or end of string), to avoid breaking
    # numbered list prefixes like "1." or "2.".
    lines = text.strip().splitlines()
    sentences = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Further split long lines on sentence boundaries:
        # period/!/? followed by space + uppercase letter
        parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', line)
        sentences.extend(parts)
    found = []
    seen = set()

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence_lower = sentence.lower()
        for keyword in keywords:
            if keyword in sentence_lower:
                if sentence_lower not in seen:
                    found.append(sentence)
                    seen.add(sentence_lower)
                break

    return found
