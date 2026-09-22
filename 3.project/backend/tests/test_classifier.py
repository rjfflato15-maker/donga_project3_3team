import os
import pytest
from backend.app.ai.classifier import classify_document
from backend.app.schemas.common import DocumentType

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sample-data")


def test_classify_all_6_documents():
    test_cases = [
        ("01_계약서_ABC홈페이지구축.txt", DocumentType.CONTRACT),
        ("02_견적서_ABC홈페이지구축.txt", DocumentType.ESTIMATE),
        ("03_사업자등록증_ABC주식회사.txt", DocumentType.BUSINESS_REGISTRATION),
        ("04_통장사본_ABC주식회사.txt", DocumentType.BANK_ACCOUNT),
        ("05_세금계산서_10450000원.txt", DocumentType.TAX_INVOICE),
        ("06_검수확인서_ABC홈페이지구축.txt", DocumentType.INSPECTION_CONFIRMATION),
    ]

    for filename, expected_type in test_cases:
        filepath = os.path.join(SAMPLE_DIR, filename)
        assert os.path.exists(filepath), f"File {filepath} must exist"
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        doc_type, confidence, breakdown = classify_document(content)
        assert doc_type == expected_type, f"Failed for {filename}: got {doc_type}, expected {expected_type}"
        assert confidence >= 0.70, f"Low confidence {confidence} for {filename}"
