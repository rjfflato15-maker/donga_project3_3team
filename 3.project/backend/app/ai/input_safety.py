"""Conservative local-document budgets, checked before expensive decoding.

These guards bound common container/image attacks. They are not a sandbox for
native PDF/Office decoders; originals still require a trusted local workflow.
"""
import io
import zipfile
import zlib
from pathlib import PurePosixPath

MIB = 1024 * 1024
MAX_ARCHIVE_MEMBERS = 2048
MAX_ARCHIVE_MEMBER_BYTES = 32 * MIB
MAX_ARCHIVE_EXPANDED_BYTES = 64 * MIB
MAX_EXTRACTED_TEXT_CHARS = 2_000_000
MAX_SPREADSHEET_CELLS = 200_000
MAX_SPREADSHEET_SHEETS = 100
MAX_IMAGE_PIXELS = 25_000_000
MAX_IMAGE_EDGE = 16_384
IMAGE_FORMATS = {'.png': {'PNG'}, '.jpg': {'JPEG'}, '.jpeg': {'JPEG'},
                 '.webp': {'WEBP'}, '.bmp': {'BMP'}, '.tif': {'TIFF'},
                 '.tiff': {'TIFF'}, '.gif': {'GIF'}}


class UnsafeDocument(ValueError):
    """Invalid or over-budget input; never downgrade to partial success."""


def check_image_size(image):
    width, height = image.size
    if (width <= 0 or height <= 0 or max(width, height) > MAX_IMAGE_EDGE
            or width * height > MAX_IMAGE_PIXELS):
        raise UnsafeDocument('이미지 크기가 안전한 처리 한도를 초과했습니다. 해상도를 줄여 다시 등록하세요.')


def check_container(source, extension):
    """Inspect ZIP metadata or image headers without expanding their payloads."""
    stream = io.BytesIO(source) if isinstance(source, (bytes, bytearray)) else source
    if extension in {'.docx', '.xlsx', '.xlsm', '.hwpx'}:
        try:
            with zipfile.ZipFile(stream) as archive:
                members = archive.infolist()
                if (len(members) > MAX_ARCHIVE_MEMBERS
                        or sum(member.file_size for member in members) > MAX_ARCHIVE_EXPANDED_BYTES
                        or any(member.file_size > MAX_ARCHIVE_MEMBER_BYTES for member in members)):
                    raise UnsafeDocument('압축 문서의 펼친 크기 또는 항목 수가 처리 한도를 초과했습니다. 문서를 나눠 등록하세요.')
                names = set()
                for member in members:
                    name = member.filename
                    path = PurePosixPath(name)
                    original = getattr(member, 'orig_filename', name)
                    if (not path.parts or path.is_absolute() or '..' in path.parts
                            or any(character in original for character in ('\\', ':', '\x00'))
                            or name.casefold() in names or member.flag_bits & 1):
                        raise UnsafeDocument('압축 문서의 경로 또는 암호 설정이 올바르지 않습니다.')
                    names.add(name.casefold())
                required = ({'[content_types].xml', 'word/document.xml'} if extension == '.docx'
                            else {'[content_types].xml', 'xl/workbook.xml'} if extension in {'.xlsx', '.xlsm'} else set())
                if extension == '.docx' and 'word/document.xml' in archive.namelist():
                    _check_docx_xml(archive.read('word/document.xml'))
                if extension in {'.xlsx', '.xlsm'}:
                    _check_spreadsheet_xml(archive, members)
                if not required <= names or (extension == '.hwpx' and not any(name.endswith('.xml') for name in names)):
                    raise UnsafeDocument('문서의 실제 형식이 확장자와 일치하지 않습니다.')
        except (zipfile.BadZipFile, OSError, ValueError) as error:
            if isinstance(error, UnsafeDocument):
                raise
            raise UnsafeDocument('압축 문서 형식을 읽을 수 없습니다.') from error
    elif extension in IMAGE_FORMATS:
        try:
            from PIL import Image
            with Image.open(stream) as image:
                check_image_size(image)
                if image.format not in IMAGE_FORMATS[extension]:
                    raise UnsafeDocument('이미지의 실제 형식이 확장자와 일치하지 않습니다.')
                image.verify()
        except Exception as error:
            if isinstance(error, UnsafeDocument):
                raise
            raise UnsafeDocument('이미지 형식을 읽을 수 없습니다.') from error




def reject_xml_entities(data):
    folded = data.lower().replace(b'\x00', b'')
    if b'<!doctype' in folded or b'<!entity' in folded:
        raise UnsafeDocument('외부 정의 또는 엔터티가 있는 문서는 처리하지 않습니다.')


def _check_docx_xml(data):
    """Grid spans multiply cells in python-docx even in tiny XML documents."""
    import xml.etree.ElementTree as ET

    reject_xml_entities(data)
    cells = 0
    try:
        for event, element in ET.iterparse(io.BytesIO(data), events=('start', 'end')):
            if event == 'end':
                element.clear()
                continue
            tag = element.tag.rsplit('}', 1)[-1]
            if tag == 'tc':
                cells += 1
            elif tag == 'gridSpan':
                value = next((value for key, value in element.attrib.items() if key.rsplit('}', 1)[-1] == 'val'), '1')
                if not value.isdecimal() or len(value) > 2 or not 1 <= int(value) <= 64:
                    raise UnsafeDocument('Word 표의 병합 범위가 처리 한도를 초과했습니다.')
                cells += int(value) - 1
            if cells > MAX_SPREADSHEET_CELLS:
                raise UnsafeDocument('Word 표의 셀 수가 처리 한도를 초과했습니다.')
    except ET.ParseError as error:
        raise UnsafeDocument('Word XML 형식이 올바르지 않습니다.') from error


def _check_spreadsheet_xml(archive, members):
    """Reject sparse/dishonest dimensions before openpyxl allocates empty rows."""
    import re
    import xml.etree.ElementTree as ET

    sheets = [member for member in members if member.filename.startswith('xl/worksheets/')
              and member.filename.endswith('.xml')]
    if len(sheets) > MAX_SPREADSHEET_SHEETS:
        raise UnsafeDocument('시트 수가 처리 한도를 초과했습니다.')
    total_cells = 0
    for member in sheets:
        # The ZIP metadata preflight above has bounded this allocation already.
        data = archive.read(member)
        # Office XML needs no DTD/entities. Reject before any XML expansion.
        reject_xml_entities(data)
        rows = columns = current_row = current_column = cell_count = 0
        try:
            for event, element in ET.iterparse(io.BytesIO(data), events=('start', 'end')):
                if event == 'end':
                    element.clear()
                    continue
                tag = element.tag.rsplit('}', 1)[-1]
                references = []
                if tag == 'dimension':
                    references = element.attrib.get('ref', '').split(':')
                elif tag == 'c':
                    cell_count += 1
                    current_column += 1
                    columns = max(columns, current_column)
                    if cell_count > MAX_SPREADSHEET_CELLS - total_cells:
                        raise UnsafeDocument('스프레드시트 셀 수가 처리 한도를 초과했습니다.')
                    references = [element.attrib.get('r', '')]
                elif tag == 'row':
                    current_row += 1
                    current_column = 0
                    number = element.attrib.get('r', str(current_row))
                    if not number.isdecimal() or len(number) > 7:
                        raise UnsafeDocument('스프레드시트 행 번호가 올바르지 않습니다.')
                    current_row = int(number)
                    rows = max(rows, current_row)
                for reference in references:
                    if not reference:
                        continue
                    match = re.fullmatch(r'([A-Za-z]{1,3})([0-9]{1,7})', reference)
                    if not match:
                        raise UnsafeDocument('스프레드시트 셀 주소가 올바르지 않습니다.')
                    column = 0
                    for character in match[1].upper():
                        column = column * 26 + ord(character) - ord('A') + 1
                    columns = max(columns, column)
                    if tag == "c":
                        current_column = column
                    rows = max(rows, int(match[2]))
                if (rows > MAX_SPREADSHEET_CELLS or columns > 16_384
                        or rows * max(columns, 1) > MAX_SPREADSHEET_CELLS - total_cells):
                    raise UnsafeDocument('스프레드시트 범위가 처리 한도를 초과했습니다. 사용하지 않는 행·열을 정리하거나 문서를 나누세요.')
        except ET.ParseError as error:
            raise UnsafeDocument('스프레드시트 XML 형식이 올바르지 않습니다.') from error
        total_cells += max(cell_count, rows * max(columns, 1))


def bounded_decompress(data, wbits):
    decoder = zlib.decompressobj(wbits)
    result = decoder.decompress(data, MAX_ARCHIVE_MEMBER_BYTES + 1)
    if len(result) > MAX_ARCHIVE_MEMBER_BYTES or decoder.unconsumed_tail:
        raise UnsafeDocument('HWP 문서의 펼친 크기가 처리 한도를 초과했습니다.')
    if not decoder.eof:
        raise zlib.error('Incomplete compressed stream')
    return result


def checked_text(text):
    if len(text) > MAX_EXTRACTED_TEXT_CHARS:
        raise UnsafeDocument('문서 텍스트가 처리 한도를 초과했습니다. 문서를 나눠 등록하세요.')
    return text


class TextBudget:
    def __init__(self):
        self.parts = []
        self.size = 0

    def append(self, text):
        self.size += len(text) + 1
        if self.size > MAX_EXTRACTED_TEXT_CHARS:
            raise UnsafeDocument('문서 텍스트가 처리 한도를 초과했습니다. 문서를 나눠 등록하세요.')
        self.parts.append(text)

    def join(self, separator='\n'):
        return separator.join(self.parts).strip()
