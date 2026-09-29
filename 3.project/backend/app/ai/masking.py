import re
from typing import Dict, List, Tuple


# Korean regions for address masking
KOREAN_REGIONS = (
    "서울특별시|서울시|서울|부산광역시|부산시|부산|대구광역시|대구시|대구|"
    "인천광역시|인천시|인천|광주광역시|광주시|광주|대전광역시|대전시|대전|"
    "울산광역시|울산시|울산|세종특별자치시|세종시|세종|경기도|경기|"
    "강원특별자치도|강원도|강원|충청북도|충북|충청남도|충남|"
    "전북특별자치도|전라북도|전북|전라남도|전남|경상북도|경북|경상남도|경남|"
    "제주특별자치도|제주도|제주"
)

# Regex Patterns
# 1. RRN: 앞 6자리 생년월일 + 구분자(선택) + 성별(1~8) + 나머지 6자리
RRN_PATTERN = re.compile(r"\b(\d{6})\s*[-–]?\s*([1-8])\d{6}\b")

# 2. Business Registration Number: 3자리-2자리-5자리
BIZ_REG_NO_PATTERN = re.compile(r"\b(\d{3})\s*[-–]\s*(\d{2})\s*[-–]\s*(\d{5})\b")
BIZ_KEYWORD_PATTERN = re.compile(
    r"((?:사업자\s*(?:등록)?\s*번호|등록번호)\s*[:：]?\s*)(\d{3})\s*[-–]?\s*(\d{2})\s*[-–]?\s*(\d{5})\b"
)

# 3. Phone & Tel patterns (Run BEFORE account pattern to avoid false matching)
PHONE_PATTERN = re.compile(r"\b(01[016789])\s*[-–.]?\s*(\d{3,4})\s*[-–.]?\s*(\d{4})\b")
TEL_PATTERN = re.compile(r"\b(02|0[3-6][1-5]|070|080)\s*[-–.]?\s*(\d{3,4})\s*[-–.]?\s*(\d{4})\b")

# 4. Email pattern
EMAIL_PATTERN = re.compile(r"\b([A-Za-z0-9._%+-]{2})[A-Za-z0-9._%+-]*(@[A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")

# 5. Account number patterns
ACCOUNT_KEYWORD_PATTERN = re.compile(
    r"((?:입금\s*계좌|환불\s*계좌|수납\s*계좌|출금\s*계좌|계좌\s*번호|계좌)\s*[:：]?\s*(?:[가-힣]+은행|[가-힣]+증권)?\s*)([0-9\-]{9,20})\b"
)
BANK_ACCOUNT_PATTERN = re.compile(
    r"((?:국민|신한|우리|하나|기업|농협|SC제일|씨티|카카오뱅크|케이뱅크|토스뱅크|우체국|새마을|신협|수협|부산|대구|경남|광주|전북|제주)은행?\s*)([0-9\-]{9,20})\b"
)
ACCOUNT_PATTERN = re.compile(r"\b(\d{3,4})\s*[-–]\s*(\d{2,6})\s*[-–]\s*(\d{3,6})\b")

# 6. Address patterns
LABELED_ADDR_PATTERN = re.compile(
    r"((?:[\(\[\<]?\s*(?:사업장\s*주소|사업장\s*소재지|본점\s*소재지|주소지|주소|소재지|거주지|자택\s*주소)\s*[\)\]\>]?\s*[:：]?\s*))("
    + KOREAN_REGIONS
    + r")\s+([^\n\r]+)"
)
STANDALONE_ADDR_PATTERN = re.compile(
    r"\b("
    + KOREAN_REGIONS
    + r")\s+([가-힣0-9\s,\-\.·~]+?(?:시|군|구|읍|면|로|길|동|리|가)\s+[0-9\-]+(?:[^\n\r,]*)?)"
)


def mask_sensitive_information(text: str) -> Tuple[str, int, List[str], Dict[str, str]]:
    """
    Masks personal and confidential information according to requested rules:
    - Resident Registration Number (RRN): YYMMDD-G****** (뒷자리 성별 구분 1자리 제외 * 표시)
    - Business Registration Number: XXX-**-***** (앞 3자리 표시, 가운데 * 표시, 끝에 번호 * 표시)
    - Bank Account Number: XXX-***-XXXX (앞 3자리 표시, 가운데 * 표시, 끝 번호 유지)
    - Address: [지역] ******* (주소지 지역만 표시하고 나머지 * 표시)
    - Phone: 010-****-XXXX
    - Email: us***@domain.com

    Returns:
        (masked_text, total_masked_count, detected_categories, token_map)
    """
    token_map: Dict[str, str] = {}
    categories_found = set()

    masked_text = text

    # 1. Resident Registration Number (RRN): 주민번호 뒷 성별 구분 제외 *표시
    def rrn_sub(match):
        birth = match.group(1)
        gender = match.group(2)
        raw = match.group(0)
        token_map[f"RRN_{len(token_map)+1}"] = raw
        categories_found.add("RRN")
        return f"{birth}-{gender}******"

    masked_text = RRN_PATTERN.sub(rrn_sub, masked_text)

    # 2. Business Registration Number: 앞 3자리 표시, 가운데 * 표시, 끝에 번호 * 표시 -> 123-**-*****
    def biz_keyword_sub(match):
        prefix = match.group(1)
        front = match.group(2)
        raw = match.group(0)
        token_map[f"BIZ_{len(token_map)+1}"] = raw
        categories_found.add("BIZ_REG_NO")
        return f"{prefix}{front}-**-*****"

    masked_text = BIZ_KEYWORD_PATTERN.sub(biz_keyword_sub, masked_text)

    def biz_sub(match):
        front = match.group(1)
        raw = match.group(0)
        token_map[f"BIZ_{len(token_map)+1}"] = raw
        categories_found.add("BIZ_REG_NO")
        return f"{front}-**-*****"

    masked_text = BIZ_REG_NO_PATTERN.sub(biz_sub, masked_text)

    # 3. Mobile / Phone numbers: PHONE_PATTERN & TEL_PATTERN must run before ACCOUNT_PATTERN
    def phone_sub(match):
        prefix = match.group(1)
        end = match.group(3)
        raw = match.group(0)
        token_map[f"PHONE_{len(token_map)+1}"] = raw
        categories_found.add("PHONE")
        return f"{prefix}-****-{end}"

    masked_text = PHONE_PATTERN.sub(phone_sub, masked_text)

    def tel_sub(match):
        prefix = match.group(1)
        end = match.group(3)
        raw = match.group(0)
        token_map[f"TEL_{len(token_map)+1}"] = raw
        categories_found.add("PHONE")
        return f"{prefix}-****-{end}"

    masked_text = TEL_PATTERN.sub(tel_sub, masked_text)

    # 4. Email: 아이디 앞 2자리 유지, 나머지 * 마스킹
    def email_sub(match):
        prefix = match.group(1)
        domain = match.group(2)
        raw = match.group(0)
        token_map[f"EMAIL_{len(token_map)+1}"] = raw
        categories_found.add("EMAIL")
        return f"{prefix}***{domain}"

    masked_text = EMAIL_PATTERN.sub(email_sub, masked_text)

    # 5. Bank Account Number: 앞에 3자리 가운데 *표시 해서 나오고 (끝에 번호는 표시)
    def mask_acc_string(raw_acc: str) -> str:
        clean = re.sub(r"\s+", "", raw_acc)
        parts = clean.split("-")
        # Exclude business registration number (3-2-5)
        if len(parts) == 3 and len(parts[0]) == 3 and len(parts[1]) == 2 and len(parts[2]) == 5:
            return raw_acc
        # Exclude phone prefixes if somehow not captured
        if parts[0] in ["010", "011", "016", "017", "018", "019", "02", "070", "080"]:
            return raw_acc

        if len(parts) >= 3:
            # First part (3-4 digits), middle part(s) replaced with *, last part preserved
            front = parts[0]
            middle_masked = "-".join("*" * len(p) for p in parts[1:-1])
            end = parts[-1]
            return f"{front}-{middle_masked}-{end}"
        elif len(parts) == 2:
            front = parts[0]
            end = parts[1]
            return f"{front}-{'*'*len(end)}"
        else:
            # No hyphen: e.g. 110123456789 (11~14 digits)
            if len(clean) >= 9:
                front = clean[:3]
                end = clean[-4:]
                middle_len = len(clean) - 7
                return f"{front}-{'*'*middle_len}-{end}"
            return raw_acc

    def acc_keyword_sub(match):
        prefix = match.group(1)
        raw_acc = match.group(2)
        masked_acc = mask_acc_string(raw_acc)
        token_map[f"ACC_{len(token_map)+1}"] = raw_acc
        categories_found.add("ACCOUNT")
        return f"{prefix}{masked_acc}"

    masked_text = ACCOUNT_KEYWORD_PATTERN.sub(acc_keyword_sub, masked_text)
    masked_text = BANK_ACCOUNT_PATTERN.sub(acc_keyword_sub, masked_text)

    def account_sub(match):
        raw = match.group(0)
        clean = re.sub(r"\s+", "", raw)
        parts = clean.split("-")
        # Ensure not business registration number (3-2-5)
        if len(parts) == 3 and len(parts[0]) == 3 and len(parts[1]) == 2 and len(parts[2]) == 5:
            return raw
        # Ensure not phone numbers
        if parts[0] in ["010", "011", "016", "017", "018", "019", "02", "031", "032", "033", "041", "042", "043", "044", "051", "052", "053", "054", "055", "061", "062", "063", "064", "070", "080"]:
            return raw

        g1 = match.group(1)
        g2 = match.group(2)
        g3 = match.group(3)
        token_map[f"ACC_{len(token_map)+1}"] = raw
        categories_found.add("ACCOUNT")
        return f"{g1}-{'*'*len(g2)}-{g3}"

    masked_text = ACCOUNT_PATTERN.sub(account_sub, masked_text)

    # 6. Address: 주소지 지역만 표시 하고 나머지 *로 표시
    def labeled_addr_sub(match):
        prefix = match.group(1)
        region = match.group(2)
        rest = match.group(3)
        raw = match.group(0)
        token_map[f"ADDR_{len(token_map)+1}"] = raw
        categories_found.add("ADDRESS")
        # Mask non-space characters with *
        masked_rest = re.sub(r"\S", "*", rest)
        return f"{prefix}{region} {masked_rest}"

    masked_text = LABELED_ADDR_PATTERN.sub(labeled_addr_sub, masked_text)

    def standalone_addr_sub(match):
        region = match.group(1)
        rest = match.group(2)
        raw = match.group(0)
        if "*" in rest:
            return raw
        token_map[f"ADDR_{len(token_map)+1}"] = raw
        categories_found.add("ADDRESS")
        masked_rest = re.sub(r"\S", "*", rest)
        return f"{region} {masked_rest}"

    masked_text = STANDALONE_ADDR_PATTERN.sub(standalone_addr_sub, masked_text)

    total_masked_count = len(token_map)
    sorted_categories = sorted(list(categories_found))

    return masked_text, total_masked_count, sorted_categories, token_map
