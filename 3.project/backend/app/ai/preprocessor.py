import os
from typing import Tuple, Any


def _to_pil_image(image_input: Any):
    """Safely converts various image input types to a PIL Image with proper orientation."""
    from PIL import Image, ImageOps
    import io

    img = None
    if isinstance(image_input, str):
        if os.path.exists(image_input):
            img = Image.open(image_input)
    elif isinstance(image_input, (bytes, bytearray)):
        img = Image.open(io.BytesIO(image_input))
    elif hasattr(image_input, "read"):
        img = Image.open(image_input)
    elif isinstance(image_input, Image.Image):
        img = image_input
    else:
        # Numpy array or similar
        try:
            img = Image.fromarray(image_input)
        except Exception:
            pass

    if img is not None:
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
    return img


def run_ocr_on_image(image_input: Any) -> str:
    """
    Runs high-accuracy OCR on image (file path, bytes, PIL Image, or numpy array).
    Uses Windows Native OCR (WinOCR) with auto-rescaling for superior Korean & English recognition.
    Falls back to PyTesseract if available.
    """
    from PIL import Image

    pil_img = _to_pil_image(image_input)

    # 1. WinOCR (Windows 10/11 native Media.Ocr Engine)
    if pil_img is not None:
        try:
            import winocr

            target_img = pil_img
            w, h = target_img.size
            if w < 1200 or h < 600:
                scale = max(2, min(4, 1600 // max(w, 1)))
                target_img = target_img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)

            res = winocr.recognize_pil_sync(target_img, lang="ko")
            if res:
                lines = [l.get("text", "").strip() for l in res.get("lines", []) if l.get("text", "").strip()]
                if lines:
                    return "\n".join(lines).strip()
                elif res.get("text", "").strip():
                    return res.get("text", "").strip()
        except Exception:
            pass

    # 2. PyTesseract fallback
    if pil_img is not None:
        try:
            import pytesseract
            ocr_text = pytesseract.image_to_string(pil_img, lang="kor+eng").strip()
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
