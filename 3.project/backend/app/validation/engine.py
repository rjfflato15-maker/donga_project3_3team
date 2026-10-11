import re
from decimal import Decimal
from typing import List, Dict, Any, Tuple
from ..schemas.common import DocumentType, ValidationStatus, CORE_6_DOCUMENT_TYPES, DOCUMENT_TYPE_KOREAN
from ..schemas.validation import ValidationCheck, ValidationSummary
from .metrics import calculate_validation_metrics
from .financial import money, document_total
from .billing import invoice_scope_checks
from ..integrations.nts_client import get_nts_client

# 법인 표기·띄어쓰기·문장부호만 다른 이름은 같은 거래처로 본다.
_ENTITY_MARKS = re.compile(r"주식회사|유한책임회사|유한회사|합자회사|합명회사|사단법인|재단법인|\((?:주|유|합|사|재)\)|㈜")


def normalize_party_name(name):
    return re.sub(r"[\s()\[\]·.,\-_]", "", _ENTITY_MARKS.sub("", name or "")).lower()


class RuleEngine:
    def __init__(self):
        self.nts_client = get_nts_client()

    def validate_contract_evidence(self, contract_id: int, contract_title: str,
                                  expected_vendor_name: str, expected_biz_no: str,
                                  contract_amount: float, documents_data: List[Dict[str, Any]],
                                  required_document_types=None, amount_policy=None) -> Tuple[ValidationSummary, List[ValidationCheck]]:
        checks = []
        required = required_document_types if required_document_types is not None else CORE_6_DOCUMENT_TYPES
        policy = amount_policy or {"amount_basis": "UNKNOWN", "payment_mode": "FULL"}
        by_type = {}
        for doc in documents_data:
            by_type.setdefault(doc.get("document_type", "unknown"), []).append(doc)
            if doc.get("file_available") is False:
                checks.append(self.check("ORIGINAL_FILE", "REVIEW", str(doc["document_id"]), "서버에 보관", "원본 없음",
                                         f"{doc.get('file_name', '문서')}: 원본을 다시 등록해야 미리보기와 다운로드가 가능합니다."))
            if doc.get("document_type") == "unknown":
                checks.append(self.check("DOCUMENT_TYPE", "REVIEW", str(doc["document_id"]), "문서 유형", "미분류", "문서 유형을 확인하세요."))
            if doc.get("processing_status") == "FAILED":
                checks.append(self.check("DOCUMENT_PROCESSING", "REVIEW", str(doc["document_id"]), "인식 완료", "인식 실패", "원본과 추출값을 직접 확인하세요."))
        for dtype in required:
            if dtype.value not in by_type:
                checks.append(self.check("REQUIRED_DOCUMENTS", "MISSING", dtype.value, "제출", "누락",
                                         f"{DOCUMENT_TYPE_KOREAN[dtype]}이(가) 제출되지 않았습니다."))
        expected_no = re.sub(r"\D", "", expected_biz_no or "")
        biz_docs = [d for d in documents_data if d["document_type"] in {"contract", "estimate", "tax_invoice", "business_registration"}]
        if not biz_docs:
            checks.append(self.check("BUSINESS_NO_MATCH", "REVIEW", "business_registration_no", expected_biz_no, "미추출", "사업자등록번호를 확인할 문서가 없습니다."))
        for doc in biz_docs:
            found = re.sub(r"\D", "", doc.get("fields", {}).get("business_registration_no") or "")
            label = doc.get("file_name", DOCUMENT_TYPE_KOREAN.get(DocumentType(doc["document_type"]), "문서"))
            if len(expected_no) != 10 or len(found) != 10:
                checks.append(self.check("BUSINESS_NO_MATCH", "REVIEW", str(doc["document_id"]), expected_biz_no, found or "미추출", f"{label}: 사업자등록번호를 확인하세요."))
            else:
                same = found == expected_no
                checks.append(self.check("BUSINESS_NO_MATCH", "PASS" if same else "FAIL", str(doc["document_id"]),
                                         expected_biz_no, found, f"{label}: 사업자등록번호가 {'일치합니다' if same else '다릅니다'}."))
        expected_name = normalize_party_name(expected_vendor_name)
        for doc in documents_data:
            fields=doc.get('fields',{});name=fields.get('company_name')
            if expected_name and name and normalize_party_name(name)!=expected_name and doc.get('document_type')!='bank_account':
                checks.append(self.check('VENDOR_NAME_MATCH','REVIEW',str(doc['document_id']),expected_vendor_name,name,
                    f"{doc.get('file_name','문서')}: 상호가 등록된 계약 거래처와 다릅니다. 오독·다른 거래처·등록 기준 오류를 확인하세요."))
            scan=(fields.get('extraction_metadata') or {}).get('automatic_source_review') or {}
            from ..services.business_identity_service import POLICY
            if scan.get('policy')!=POLICY or scan.get('source_sha256')!=doc.get('sha256') or scan.get('kind')!=doc.get('document_type') or scan.get('method')!='RASTER_OCR_ROW_CROP':continue
            source=scan.get('identity') or {}
            for field in scan.get('verified_fields') or []:
                expected_value=source.get('name') if field=='company_name' else source.get('number') if field=='business_registration_no' else (source.get('financial') or {}).get(field)
                current_value=fields.get(field)
                if expected_value is None:continue
                if field=='company_name':same=normalize_party_name(current_value)==expected_value;expected_display=expected_value
                elif field=='business_registration_no':same=re.sub(r'[\s-]','',str(current_value or ''))==expected_value;expected_display=expected_value
                else:same=money(current_value)==money(expected_value);expected_display=self.fmt(money(expected_value))
                if not same:
                    actual_display=self.fmt(money(current_value)) if field.endswith('amount') and money(current_value) is not None else str(current_value or '미추출')
                    checks.append(self.check('SOURCE_VALUE_MATCH_'+field.upper(),'REVIEW',str(doc['document_id']),expected_display,actual_display,
                        f"{doc.get('file_name','문서')}: 스캔 원문 행 재판독과 저장값이 다릅니다. 해당 원문을 확인해 오독을 정정하세요."))
        for doc in by_type.get("bank_account", []):
            holder = (doc.get("fields", {}).get("company_name") or "").strip()
            label = doc.get("file_name", "통장사본")
            if not expected_name or not normalize_party_name(holder):
                checks.append(self.check("ACCOUNT_HOLDER_MATCH", "REVIEW", str(doc["document_id"]), expected_vendor_name or "미등록",
                                         holder if normalize_party_name(holder) else "미추출", f"{label}: 예금주를 원문에서 확인하세요."))
            elif normalize_party_name(holder) == expected_name:
                checks.append(self.check("ACCOUNT_HOLDER_MATCH", "PASS", str(doc["document_id"]), expected_vendor_name, holder,
                                         f"{label}: 예금주가 계약 거래처와 일치합니다."))
            else:
                # 개인사업자는 대표자 개인 명의 계좌를 쓰기도 하므로 FAIL이 아니라 사람 확인으로 둔다.
                checks.append(self.check("ACCOUNT_HOLDER_MATCH", "REVIEW", str(doc["document_id"]), expected_vendor_name, holder,
                                         f"{label}: 예금주가 계약 거래처와 다릅니다. 개인사업자 대표자 명의인지, 계좌가 바뀐 것은 아닌지 거래처에 확인하세요."))
        nts = self.nts_client.check_business_status(expected_biz_no)
        if not nts.get("verified"):
            checks.append(self.check("BUSINESS_STATUS", "REVIEW", "business_status", "실제 조회", nts.get("status", "확인 불가"),
                                     nts.get("detail", "국세청 영업 상태를 확인하지 못했습니다.") + " 세금계산서 진위 검증 기능은 아닙니다."))
        else:
            checks.append(self.check("BUSINESS_STATUS", "PASS" if nts.get("is_active") else "FAIL", "business_status",
                                     "계속사업자", nts["status"], "사업자 영업 상태 실제 조회 결과입니다."))
        expected = money(contract_amount)
        if policy.get("amount_basis") == "SUPPLY":
            tax = money(policy.get("tax_amount"))
            expected = expected + tax if expected is not None and tax is not None else None
        elif policy.get("amount_basis") != "TOTAL":
            expected = None
        if expected is None or expected <= 0:
            checks.append(self.check("AMOUNT_BASIS", "REVIEW", "amount_basis", "합계 기준", "기준 미확인",
                                     "계약금액의 부가세 포함 여부와 세액을 확인하세요. 임의로 세율을 적용하지 않습니다."))
        amounts = {}
        for dtype in ("estimate", "tax_invoice"):
            rows = by_type.get(dtype, [])
            amounts[dtype] = []
            if dtype in [t.value for t in required] and not rows:
                continue
            for doc in rows:
                fields = doc.get("fields", {})
                total = document_total(fields)
                supply, tax = money(fields.get("supply_amount")), money(fields.get("tax_amount"))
                label = doc.get("file_name", dtype)
                if total is not None and supply is not None and tax is not None and total != supply + tax:
                    checks.append(self.check("AMOUNT_COMPONENTS", "FAIL", str(doc["document_id"]), self.fmt(supply + tax),
                                             self.fmt(total), f"{label}: 공급가액과 세액의 합이 표시된 합계와 다릅니다."))
                if total is None:
                    checks.append(self.check("AMOUNT_EXTRACTION", "REVIEW", str(doc["document_id"]), "공급가액·세액·합계", "기준 미확인",
                                             f"{label}: 금액 의미를 확인하고 추출값을 보완하세요."))
                    continue
                amounts[dtype].append((doc, total))
                if expected is None:
                    continue
                if dtype == "tax_invoice" and policy.get("payment_mode") == "INSTALLMENT" and total != expected:
                    continue
                same = total == expected
                status = "PASS" if same else "FAIL"
                if not same and dtype == "tax_invoice" and fields.get("amount_scope") != "FULL":
                    status = "REVIEW"
                checks.append(self.check("AMOUNT_MATCH_" + dtype.upper(), status, str(doc["document_id"]), self.fmt(expected),
                                         self.fmt(total), f"{label}: 합계 기준 {'금액 일치' if same else self.fmt(abs(total - expected)) + ' 차이'}."))
        invoices = amounts.get("tax_invoice", [])
        if expected is not None:
            checks.extend(invoice_scope_checks(self, invoices, expected, documents_data, policy))
        if policy.get("payment_mode") == "INSTALLMENT" and invoices and expected is not None:
            hashes = [doc.get("sha256") for doc, _ in invoices if doc.get("sha256")]
            if len(hashes) != len(set(hashes)):
                checks.append(self.check("DUPLICATE_INVOICE", "REVIEW", "tax_invoice", "서로 다른 문서", "중복 파일", "중복 세금계산서를 제거한 후 누적 금액을 확인하세요."))
            elif len(invoices) > 1 and any(d.get('fields', {}).get('amount_scope') == 'FULL' for d, _ in invoices):
                checks.append(self.check('PAYMENT_SCOPE', 'REVIEW', 'tax_invoice', '중복되지 않는 회차별 청구', '전액·회차 청구 혼재',
                    '전액 청구와 다른 계산서가 함께 있습니다. 전체 금액을 담은 계산서와 회차별 계산서가 겹치는지 확인하세요. 확인 전 임의로 합산하지 않습니다.'))
            elif not any(d.get('fields', {}).get('amount_scope') == 'FULL' and value < expected for d, value in invoices):
                total = sum((v for _, v in invoices), Decimal("0"))
                checks.append(self.check("INSTALLMENT_TOTAL", "PASS" if total == expected else ("FAIL" if total > expected else "REVIEW"),
                                         "tax_invoice", self.fmt(expected), self.fmt(total),
                                         "서로 다른 계산서의 청구액 누적 합계입니다. 계약금액보다 작으면 이전·추가 청구 여부를 확인하세요. 지급 완료는 별도 기록입니다."))
        submitted = sum(1 for dtype in required if dtype.value in by_type)
        return calculate_validation_metrics(len(required), submitted, checks), checks

    @staticmethod
    def fmt(value):
        return f"{value:,.0f}원"

    @staticmethod
    def check(rule, status, field, expected, actual, message):
        return ValidationCheck(rule_id=rule, status=ValidationStatus(status), field=field,
                               expected=expected, actual=actual, message=message)
