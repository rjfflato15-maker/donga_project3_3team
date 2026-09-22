import os
import tempfile
import pytest
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter
from backend.app.ai import analyze_document, extract_text_from_file
from backend.app.ai.classifier import classify_document
from backend.app.schemas.common import DocumentType


def create_sample_pdf(file_path: str, text_content: str):
    """Creates a simple PDF file containing the given text using pypdf."""
    from pypdf import PageObject
    # We can create a simple PDF with pypdf or pdfplumber/reportlab or standard PDF stream
    # A minimal valid PDF structure with stream content:
    pdf_content = f"""%PDF-1.4
1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj
2 0 obj <</Type /Pages /Kinds /Page /Count 1 /Kids [3 0 R]>> endobj
3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj
4 0 obj <</Length {len(text_content) + 50}>> stream
BT /F1 12 Tf 100 700 Td ({text_content}) Tj ET
endstream endobj
5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000133 00000 n 
0000000257 00000 n 
0000000360 00000 n 
trailer <</Size 6 /Root 1 0 R>>
startxref
430
%%EOF"""
    with open(file_path, "wb") as f:
        f.write(pdf_content.encode("latin-1", errors="ignore"))


def create_sample_image(file_path: str, text_content: str):
    """Creates a simple PNG image file."""
    img = Image.new("RGB", (600, 200), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), text_content, fill=(0, 0, 0))
    img.save(file_path)


def test_pdf_document_extraction_and_classification():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test 1: PDF contract
        pdf_path = os.path.join(tmp_dir, "01_계약서_테스트.pdf")
        create_sample_pdf(pdf_path, "Standard Service Contract (계약서)")
        
        extracted_text, file_type = extract_text_from_file(pdf_path, file_name="01_계약서_테스트.pdf")
        assert file_type == "pdf"
        assert "[파일명: 01_계약서_테스트.pdf]" in extracted_text

        analysis_res, raw_text, masked_text = analyze_document(pdf_path, file_name="01_계약서_테스트.pdf")
        assert analysis_res.document_type == DocumentType.CONTRACT

        # Test 2: PDF business registration
        biz_pdf_path = os.path.join(tmp_dir, "03_사업자등록증_테스트.pdf")
        create_sample_pdf(biz_pdf_path, "Business Registration Certificate")
        analysis_res, raw_text, masked_text = analyze_document(biz_pdf_path, file_name="03_사업자등록증_테스트.pdf")
        assert analysis_res.document_type == DocumentType.BUSINESS_REGISTRATION


def test_image_document_extraction_and_classification():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Test 1: PNG tax invoice
        png_path = os.path.join(tmp_dir, "05_세금계산서.png")
        create_sample_image(png_path, "Tax Invoice Sample")

        extracted_text, file_type = extract_text_from_file(png_path, file_name="05_세금계산서.png")
        assert file_type == "png"
        assert "[파일명: 05_세금계산서.png]" in extracted_text

        analysis_res, raw_text, masked_text = analyze_document(png_path, file_name="05_세금계산서.png")
        assert analysis_res.document_type == DocumentType.TAX_INVOICE

        # Test 2: JPG bank account copy
        jpg_path = os.path.join(tmp_dir, "04_통장사본.jpg")
        create_sample_image(jpg_path, "Bank Account Copy")

        analysis_res, raw_text, masked_text = analyze_document(jpg_path, file_name="04_통장사본.jpg")
        assert analysis_res.document_type == DocumentType.BANK_ACCOUNT
