import re
from typing import Dict, List, Tuple


# Patterns for Korean sensitive personal information
RRN_PATTERN = re.compile(r"\b\d{6}\s*[-–]\s*[1-4]\d{6}\b")
PHONE_PATTERN = re.compile(r"\b01[016789]\s*[-–.]?\s*\d{3,4}\s*[-–.]?\s*\d{4}\b")
TEL_PATTERN = re.compile(r"\b(02|0[3-6][1-5])\s*[-–.]?\s*\d{3,4}\s*[-–.]?\s*\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
ACCOUNT_PATTERN = re.compile(r"\b\d{3,6}\s*[-–]\s*\d{2,6}\s*[-–]\s*\d{3,6}\b")
BIZ_REG_NO_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{5}\b")


def mask_sensitive_information(text: str) -> Tuple[str, int, List[str], Dict[str, str]]:
    """
    Masks personal and confidential information according to guidelines:
    - Resident Registration Number: [RRN_001]
    - Phone/Mobile Number: [PHONE_001]
    - Email: [EMAIL_001]
    - Bank Account Number: [ACCOUNT_001]

    Preserves:
    - Business Registration Number (123-45-67890)
    - Company names, amounts, dates

    Returns:
        (masked_text, total_masked_count, detected_categories, token_map)
    """
    token_map: Dict[str, str] = {}
    categories_found = set()
    category_counts: Dict[str, int] = {
        "RRN": 0,
        "PHONE": 0,
        "EMAIL": 0,
        "ACCOUNT": 0,
    }

    # Helper to generate or reuse token for identical strings
    def get_token(category: str, raw_val: str) -> str:
        # Check if already mapped
        for tok, val in token_map.items():
            if val == raw_val and tok.startswith(f"[{category}_"):
                return tok
        category_counts[category] += 1
        tok = f"[{category}_{category_counts[category]:03d}]"
        token_map[tok] = raw_val
        categories_found.add(category)
        return tok

    masked_text = text

    # 1. RRN
    def rrn_sub(match):
        raw = match.group(0)
        return get_token("RRN", raw)
    masked_text = RRN_PATTERN.sub(rrn_sub, masked_text)

    # 2. Email
    def email_sub(match):
        raw = match.group(0)
        return get_token("EMAIL", raw)
    masked_text = EMAIL_PATTERN.sub(email_sub, masked_text)

    # 3. Mobile / Phone numbers
    def phone_sub(match):
        raw = match.group(0)
        return get_token("PHONE", raw)
    masked_text = PHONE_PATTERN.sub(phone_sub, masked_text)

    # 4. Bank Account numbers (exclude business registration numbers: 3 digits - 2 digits - 5 digits)
    def account_sub(match):
        raw = match.group(0)
        clean = re.sub(r"\s+", "", raw)
        parts = clean.split("-")
        if len(parts) == 3 and len(parts[0]) == 3 and len(parts[1]) == 2 and len(parts[2]) == 5:
            # This is a business registration number! Do NOT mask as account
            return raw
        return get_token("ACCOUNT", raw)

    masked_text = ACCOUNT_PATTERN.sub(account_sub, masked_text)

    # 5. Telephone numbers (if not already masked)
    masked_text = TEL_PATTERN.sub(phone_sub, masked_text)

    total_masked_count = len(token_map)
    sorted_categories = sorted(list(categories_found))

    return masked_text, total_masked_count, sorted_categories, token_map
