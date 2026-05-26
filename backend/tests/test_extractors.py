from app.extractors.lab import extract_lab_tests
from app.extractors.radiology import extract_radiology
from app.extractors.followup import extract_followups


def test_extract_lab_tests_finds_cbc():
    text = "Patient is advised to do a CBC blood test and check hemoglobin levels."
    results = extract_lab_tests(text)
    assert len(results) >= 1
    assert any("cbc" in r.lower() or "blood test" in r.lower() for r in results)


def test_extract_lab_tests_empty_when_no_match():
    text = "Patient should rest and drink water."
    results = extract_lab_tests(text)
    assert results == []


def test_extract_radiology_finds_xray():
    text = "Doctor recommends a chest x-ray and MRI of the knee."
    results = extract_radiology(text)
    assert len(results) >= 1
    assert any("x-ray" in r.lower() or "mri" in r.lower() for r in results)


def test_extract_radiology_empty_when_no_match():
    text = "Take paracetamol twice daily."
    results = extract_radiology(text)
    assert results == []


def test_extract_followups_finds_review():
    text = "Please follow up with the specialist. Review in 2 weeks."
    results = extract_followups(text)
    assert len(results) >= 1
    assert any("follow" in r.lower() or "review" in r.lower() for r in results)


def test_extract_followups_empty_when_no_match():
    text = "Diagnosis: viral fever. Prescription: rest."
    results = extract_followups(text)
    assert results == []


def test_no_duplicate_sentences():
    # Same sentence repeated twice — dedup logic must return it only once
    text = "CBC blood test ordered.\nCBC blood test ordered."
    results = extract_lab_tests(text)
    assert len(results) == 1
