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


def extract_text_from_docx(file_path: str) -> str:
    """Extracts text from Word .docx file (paragraphs and tables)."""
    try:
        import docx
        doc = docx.Document(file_path)
        parts = []
        for p in doc.paragraphs:
            t = p.text.strip()
            if t:
                parts.append(t)
        for tbl in doc.tables:
            for row in tbl.rows:
                row_cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if row_cells:
                    # dedup adjacent identical cells caused by merges
                    deduped = []
                    for c in row_cells:
                        if not deduped or deduped[-1] != c:
                            deduped.append(c)
                    parts.append("\t".join(deduped))
        return "\n".join(parts).strip()
    except Exception as e:
        return ""


def extract_text_from_doc(file_path: str) -> str:
    """Extracts text from legacy Word .doc format using olefile and string decoding."""
    try:
        import olefile
        if olefile.isOleFile(file_path):
            ole = olefile.OleFileIO(file_path)
            if ole.exists("WordDocument"):
                raw = ole.openstream("WordDocument").read()
                ole.close()
                u16 = raw.decode("utf-16le", errors="ignore")
                clean_lines = [l.strip() for l in u16.split("\n") if len(l.strip()) > 3]
                if clean_lines:
                    return "\n".join(clean_lines).strip()
    except Exception:
        pass

    try:
        with open(file_path, "rb") as f:
            raw = f.read()
        u16 = raw.decode("utf-16le", errors="ignore")
        clean = [l.strip() for l in u16.split("\n") if len(l.strip()) > 3]
        if clean:
            return "\n".join(clean).strip()
        return raw.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def extract_text_from_hwpx(file_path: str) -> str:
    """Extracts text from Hancom .hwpx XML package."""
    import zipfile
    import xml.etree.ElementTree as ET
    import re

    text_parts = []
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            section_files = sorted(
                [f for f in zf.namelist() if f.startswith("Contents/section") and f.endswith(".xml")]
            )
            if not section_files:
                section_files = sorted(
                    [f for f in zf.namelist() if f.endswith(".xml") and not f.startswith("META-INF") and "version" not in f.lower()]
                )

            for sf in section_files:
                try:
                    xml_data = zf.read(sf)
                    sec_text = ""
                    # 1. Try ElementTree
                    try:
                        root = ET.fromstring(xml_data)
                        paras = [elem for elem in root.iter() if elem.tag.endswith("}p") or elem.tag == "p"]
                        if paras:
                            lines = ["".join(p.itertext()).strip() for p in paras if "".join(p.itertext()).strip()]
                            sec_text = "\n".join(lines)
                        else:
                            sec_text = "".join(root.itertext()).strip()
                    except Exception:
                        pass

                    # 2. Regex fallback for unbound prefixes / namespaces
                    if not sec_text:
                        decoded = xml_data.decode("utf-8", errors="ignore")
                        t_matches = re.findall(r"<[^>]*:?t[^>]*>(.*?)</[^>]*:?t>", decoded, flags=re.DOTALL)
                        if t_matches:
                            lines = [re.sub(r"<[^>]+>", "", m).strip() for m in t_matches if m.strip()]
                            sec_text = "\n".join(lines)
                        else:
                            text_only = re.sub(r"<[^>]+>", " ", decoded)
                            lines = [l.strip() for l in text_only.split("\n") if l.strip()]
                            sec_text = "\n".join(lines)

                    if sec_text:
                        text_parts.append(sec_text)
                except Exception:
                    continue
    except Exception:
        pass

    return "\n\n".join(text_parts).strip()


def extract_text_from_hwp(file_path: str) -> str:
    """Extracts text from Hancom .hwp binary format (HWP 5.0 OLE + zlib / pyhwp / string scanning)."""
    import zlib
    extracted_text = []

    # 1. Try standard HWP 5.0 BodyText streams via olefile + zlib decompress
    try:
        import olefile
        if olefile.isOleFile(file_path):
            ole = olefile.OleFileIO(file_path)
            section_names = []
            for stream in ole.listdir():
                if len(stream) >= 2 and stream[0] == "BodyText" and stream[1].startswith("Section"):
                    section_names.append("/".join(stream))
            section_names.sort()

            for sec_name in section_names:
                try:
                    stream_data = ole.openstream(sec_name).read()
                    try:
                        decompressed = zlib.decompress(stream_data, -15)
                    except Exception:
                        try:
                            decompressed = zlib.decompress(stream_data)
                        except Exception:
                            decompressed = stream_data

                    offset = 0
                    sec_text = []
                    while offset < len(decompressed) - 4:
                        header = int.from_bytes(decompressed[offset:offset+4], "little")
                        tag_id = header & 0x3FF
                        size = (header >> 20) & 0xFFF
                        offset += 4
                        if size == 0xFFF:
                            if offset + 4 > len(decompressed):
                                break
                            size = int.from_bytes(decompressed[offset:offset+4], "little")
                            offset += 4
                        if offset + size > len(decompressed):
                            break
                        payload = decompressed[offset:offset+size]
                        offset += size

                        if tag_id == 67:  # HWPTAG_PARA_TEXT
                            chars = []
                            for i in range(0, len(payload) - 1, 2):
                                code = int.from_bytes(payload[i:i+2], "little")
                                if code in (10, 13):
                                    chars.append("\n")
                                elif code >= 32:
                                    chars.append(chr(code))
                            line = "".join(chars).strip()
                            if line:
                                sec_text.append(line)

                    if sec_text:
                        extracted_text.append("\n".join(sec_text))
                except Exception:
                    continue
            ole.close()
    except Exception:
        pass

    # 2. Try pyhwp cli tool as secondary
    if not extracted_text:
        try:
            import subprocess
            res = subprocess.run(["hwp5txt", file_path], capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass

    # 3. String scanning fallback for UTF-16LE text
    if not extracted_text:
        try:
            with open(file_path, "rb") as f:
                raw_bytes = f.read()
            u16 = raw_bytes.decode("utf-16le", errors="ignore")
            clean_lines = [line.strip() for line in u16.split("\n") if len(line.strip()) > 3]
            if clean_lines:
                extracted_text.append("\n".join(clean_lines))
        except Exception:
            pass

    return "\n\n".join(extracted_text).strip()


def extract_text_from_xlsx(file_path: str) -> str:
    """Extracts text from Excel .xlsx / .xlsm spreadsheet."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        sheet_texts = []
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            row_lines = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(cell).strip() for cell in row if cell is not None and str(cell).strip() != ""]
                if cells:
                    row_lines.append("\t".join(cells))
            if row_lines:
                sheet_texts.append(f"[시트: {sheet_name}]\n" + "\n".join(row_lines))
        wb.close()
        return "\n\n".join(sheet_texts).strip()
    except Exception:
        return ""


def extract_text_from_xls(file_path: str) -> str:
    """Extracts text from legacy Excel .xls spreadsheet."""
    try:
        import xlrd
        wb = xlrd.open_workbook(file_path)
        sheet_texts = []
        for sheet in wb.sheets():
            row_lines = []
            for row_idx in range(sheet.nrows):
                row_vals = sheet.row_values(row_idx)
                cells = [str(val).strip() for val in row_vals if val is not None and str(val).strip() != ""]
                if cells:
                    row_lines.append("\t".join(cells))
            if row_lines:
                sheet_texts.append(f"[시트: {sheet.name}]\n" + "\n".join(row_lines))
        return "\n\n".join(sheet_texts).strip()
    except Exception:
        return ""


def extract_text_from_csv(file_path: str) -> str:
    """Extracts text from .csv spreadsheet with multi-encoding detection."""
    import csv
    encodings = ["utf-8-sig", "cp949", "euc-kr", "utf-8"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f)
                lines = []
                for row in reader:
                    cells = [c.strip() for c in row if c.strip()]
                    if cells:
                        lines.append("\t".join(cells))
                if lines:
                    return "\n".join(lines).strip()
        except Exception:
            continue
    return ""


def extract_text_from_file(file_path: str, file_name: str = "") -> Tuple[str, str]:
    """
    Extracts text from various file formats:
    - PDF (.pdf)
    - Images (.png, .jpg, .jpeg, .bmp, .webp, .tiff, .tif, .gif)
    - Word (.docx, .doc)
    - Hancom (.hwp, .hwpx)
    - Excel (.xlsx, .xls, .csv)
    - Plain text (.txt, .md, .json)
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

        # 3rd attempt: Scanned PDF pages OCR via pypdfium2 + WinOCR/PyTesseract
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

    # 2. Image files (.png, .jpg, .jpeg, .bmp, .webp, .tiff, .tif, .gif)
    if ext in [".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif", ".gif"]:
        ocr_text = run_ocr_on_image(file_path)
        full_text = header + (ocr_text if ocr_text else "")
        return full_text.strip(), ext.replace(".", "")

    # 3. Word files (.docx, .doc)
    if ext == ".docx":
        docx_text = extract_text_from_docx(file_path)
        return (header + docx_text).strip(), "docx"
    if ext == ".doc":
        doc_text = extract_text_from_doc(file_path)
        return (header + doc_text).strip(), "doc"

    # 4. Hancom files (.hwpx, .hwp)
    if ext == ".hwpx":
        hwpx_text = extract_text_from_hwpx(file_path)
        return (header + hwpx_text).strip(), "hwpx"
    if ext == ".hwp":
        hwp_text = extract_text_from_hwp(file_path)
        return (header + hwp_text).strip(), "hwp"

    # 5. Excel files (.xlsx, .xlsm, .xls, .csv)
    if ext in [".xlsx", ".xlsm"]:
        xlsx_text = extract_text_from_xlsx(file_path)
        return (header + xlsx_text).strip(), "xlsx"
    if ext == ".xls":
        xls_text = extract_text_from_xls(file_path)
        return (header + xls_text).strip(), "xls"
    if ext == ".csv":
        csv_text = extract_text_from_csv(file_path)
        return (header + csv_text).strip(), "csv"

    # 6. Default text reading with encoding fallback
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr", "latin-1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                content = f.read()
                return (header + content).strip(), ext.replace(".", "") or "txt"
        except (UnicodeDecodeError, Exception):
            continue

    # 7. Binary fallback
    with open(file_path, "rb") as f:
        raw = f.read()
        return (header + raw.decode("utf-8", errors="ignore")).strip(), "bin"

