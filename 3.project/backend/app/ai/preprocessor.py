import os
from typing import Tuple, Any


def run_ocr_on_image(image_input: Any) -> str:
    """
    Runs OCR on PIL Image, file path, or numpy array.
    Uses RapidOCR as primary engine, with fallbacks to pytesseract/easyocr.
    """
    # 1. RapidOCR (Fast, local ONNX model)
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        result, _ = engine(image_input)
        if result:
            lines = [item[1] for item in result if len(item) > 1 and item[1]]
            ocr_text = "\n".join(lines).strip()
            if ocr_text:
                return ocr_text
    except Exception:
        pass

    # 2. PyTesseract fallback
    try:
        from PIL import Image
        import pytesseract
        if isinstance(image_input, str):
            img = Image.open(image_input)
        else:
            img = image_input
        ocr_text = pytesseract.image_to_string(img, lang="kor+eng").strip()
        if ocr_text:
            return ocr_text
    except Exception:
        pass

    return ""


def extract_text_from_file(file_path: str, file_name: str = "") -> Tuple[str, str]:
    """
    Extracts text from various file formats (.txt, .pdf, .png, .jpg, .md, etc.)
    Returns (extracted_text, file_type)
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if not file_name:
        file_name = os.path.basename(file_path)

    ext = os.path.splitext(file_path)[1].lower()
    header = f"[파일명: {file_name}]\n"

    # 1. PDF Files
    if ext == ".pdf":
        pdf_text = ""
        # 1st attempt: pypdf
        try:
            import pypdf
            reader = pypdf.PdfReader(file_path)
            pages_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text and text.strip():
                    pages_text.append(text)
            pdf_text = "\n\n".join(pages_text).strip()
        except Exception:
            pdf_text = ""

        # 2nd attempt: pdfplumber fallback if pypdf was empty or sparse
        if not pdf_text:
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    pages_text = [p.extract_text() for p in pdf.pages if p.extract_text()]
                pdf_text = "\n\n".join(pages_text).strip()
            except Exception:
                pdf_text = ""

        # 3rd attempt: Scanned PDF pages OCR via pypdfium2 + RapidOCR
        if not pdf_text:
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(file_path)
                ocr_pages = []
                for page in pdf:
                    pil_image = page.render(scale=2).to_pil()
                    page_ocr = run_ocr_on_image(pil_image)
                    if page_ocr:
                        ocr_pages.append(page_ocr)
                pdf_text = "\n\n".join(ocr_pages).strip()
            except Exception:
                pass

        full_text = header + (pdf_text if pdf_text else "")
        return full_text.strip(), "pdf"

    # 2. Image files (.png, .jpg, .jpeg, .bmp, .webp, .tiff, .tif)
    if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"]:
        ocr_text = run_ocr_on_image(file_path)
        full_text = header + (ocr_text if ocr_text else "")
        return full_text.strip(), ext.replace(".", "")

    # 3. Default text reading with encoding fallback
    encodings = ["utf-8", "cp949", "euc-kr", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
                return (header + content).strip(), ext.replace(".", "")
        except (UnicodeDecodeError, Exception):
            continue

    # 4. Binary fallback
    with open(file_path, "rb") as f:
        raw = f.read()
        return (header + raw.decode("utf-8", errors="ignore")).strip(), "bin"
