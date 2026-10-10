"""DEV2 guard policy. Literal anchors and field/party meaning remain mandatory.

The original v3 policy is imported for formatting and native DOCX anchors only.
No gold labels, registered amounts, other documents or heldout examples enter it.
"""
import re
from decimal import Decimal
from . import grounding as v3

GUARD_VERSION = 'grounding-v4-claim-context-20261010'
LABELS = dict(v3.LABELS)
LABELS.update(
    supply_amount=r'세전\s*대금|공급\s*가액|공급\s*금액',
    tax_amount=r'부가\s*세액|부가\s*가치세|부가세|세액',
    total_amount=r'총\s*청구액|' + v3.LABELS['total_amount'],
)
PATTERNS = {field:re.compile(r'(?<![가-힣A-Za-z0-9])(?:' + pattern + r')(?![가-힣A-Za-z0-9])')
            for field,pattern in LABELS.items()}
NEXT_LABEL = re.compile(r'(?<![가-힣A-Za-z0-9])(?:(?:공급받는자|매입자|발주자|공급자|매출자|수급인|계약상대자)\s+)?(?:' + '|'.join(
    '(?:'+pattern+')' for field,pattern in LABELS.items() if field != 'amount_scope') + r')\s*[:：=]')
MONEY_FIELDS = {'supply_amount','tax_amount','total_amount'}


def party_at_label(lines, index, end, document_type):
    party = v3.party_at(lines, index-1, document_type) if index else 'unknown'
    markers = [(m.start(),'buyer') for m in v3.BUYER.finditer(lines[index][:end])]
    markers += [(m.start(),'supplier') for m in v3.SUPPLIER.finditer(lines[index][:end])]
    if markers:
        party = max(markers)[1]
    if party == 'unknown' and document_type in {'business_registration','bank_account','inspection_confirmation'}:
        party = 'supplier'
    return party


def candidates(pages, field, document_type):
    found = []
    totals = candidates(pages,'total_amount',document_type) if field == 'amount_scope' else []
    for page in pages:
        lines = page['text'].splitlines()
        for index,line in enumerate(lines):
            for label in PATTERNS[field].finditer(line):
                tail = re.sub(r'^\s*(?:[:：=]|[.。•·](?=\s))?\s*','',line[label.end():])
                following = NEXT_LABEL.search(tail)
                if following:
                    tail = tail[:following.start()].strip()
                value_index = index
                if field != 'amount_scope' and not tail and index+1 < len(lines):
                    following_line = lines[index+1]
                    if any(p.search(following_line) for p in PATTERNS.values()) or v3.BUYER.search(following_line) or v3.SUPPLIER.search(following_line):
                        continue
                    tail = following_line.strip()
                    value_index += 1
                value = None
                if field in MONEY_FIELDS:
                    match = re.match(r'(?:[₩￦]|금)?\s*('+v3.MONEY_TOKEN+r')(?![\d,])',tail)
                    if match and not re.match(r'\s*(?:[%년월일]|[./-]\s*\d|\d)',tail[match.end():]):
                        value = match.group(1)
                        if ' ' in value and not (re.match(r'\s*원(?:$|\s|[.,(])',tail[match.end():]) or re.match(r'[₩￦]',tail)):
                            value = None
                    if field == 'total_amount' and re.search(r'부가세\s*(?:별도|미포함)|VAT\s*(?:별도|제외)|공급가액\s*기준',line,re.I):
                        value = None
                elif field == 'business_registration_no':
                    match = re.match(r'(\d{3}[\s-]*\d{2}[\s-]*\d{5})(?!\d)',tail)
                    value = match.group(1) if match else None
                elif field == 'issue_date':
                    match = re.match(r'(\d{4}\s*[년./-]\s*\d{1,2}\s*[월./-]\s*\d{1,2}\s*일?)',tail)
                    value = match.group(1) if match else None
                elif field == 'company_name':
                    value = tail.strip() or None
                else:
                    if re.fullmatch(r'계약서|견적서|검수확인서',label.group()) and not totals:
                        continue
                    from ..validation.billing import scope_in_document
                    value = scope_in_document(line, document_type, bool(totals))
                    if value == 'UNKNOWN':
                        continue
                token = v3.canonical(field,value)
                if token is not None:
                    found.append({'value':token,'page':page['page'],'line':value_index+1,'label_line':index+1,
                                  'label':label.group(),'party':party_at_label(lines,index,label.end(),document_type)})
    return found


def in_quote(field, token, quote):
    if field in MONEY_FIELDS:
        return any(v3.canonical(field,m.group())==token for m in re.finditer(r'(?<!\d)'+v3.MONEY_TOKEN+r'(?![\d,])',quote))
    if field == 'business_registration_no':
        return any(v3.canonical(field,m.group())==token for m in re.finditer(r'\d{3}[\s-]*\d{2}[\s-]*\d{5}',quote))
    if field == 'issue_date':
        return any(v3.canonical(field,m.group())==token for m in re.finditer(r'\d{4}\s*[년./-]\s*\d{1,2}\s*[월./-]\s*\d{1,2}\s*일?',quote))
    return bool(token and token in (v3.canonical(field,quote) or ''))


def guard_proposal(field, proposal, pages, document_type):
    rejected = v3.proposal_preflight(field, proposal, pages)
    if rejected:
        return rejected
    reasons, warnings, anchor = [], [], None
    state, value = proposal.get('state'),proposal.get('value')
    token = v3.canonical(field,value)
    options = candidates(pages,field,document_type)
    identity = field in {'company_name','business_registration_no'}
    eligible = [o for o in options if not identity or o['party']=='supplier']
    distinct = {o['value'] for o in eligible}
    if state in {'ABSENT','REVIEW'}:
        if value not in (None,''):
            reasons.append('INVALID_FORMAT')
        if (state=='ABSENT' and options) or (state=='REVIEW' and len(distinct)==1):
            reasons.append('UNSUPPORTED_ABSTENTION')
        if state=='ABSENT' and field in MONEY_FIELDS | {'amount_scope'}:
            if document_type in {'contract','estimate','tax_invoice','inspection_confirmation'}:
                reasons.append('UNVERIFIED_ABSENCE')
            if any(re.search(r'참고값\s*[A-ZＡ-Ｚ]?\s*[:：.]?\s*\d',p['text']) for p in pages):
                reasons.append('AMBIGUOUS_UNLABELED_AMOUNT')
    else:
        if state!='VALUE' or token is None:
            reasons.append('INVALID_FORMAT')
        page_no, line_no, quote = proposal.get('page'),proposal.get('line'),proposal.get('quote','')
        if (field=='amount_scope' and state=='VALUE' and page_no is None and line_no is None and not quote
                and len(distinct)==1 and token in distinct and len({o['value'] for o in candidates(pages,'total_amount',document_type)})==1):
            o=eligible[0]; page_no,line_no=o['page'],o['line']
            page=next(p for p in pages if p['page']==page_no)
            quote=page['text'].splitlines()[line_no-1]
            warnings.append('CODE_ANCHORED_SCOPE')
        page=next((p for p in pages if p['page']==page_no),None)
        structural=bool(page and page.get('document_format')=='docx')
        if not page or not structural and (page_no is None or page['location_kind']!='page'):
            reasons.append('PAGE_UNVERIFIED')
        matches=[]
        if page and type(line_no) is int and line_no>=1 and isinstance(quote,str) and quote:
            lines=page['text'].splitlines(); choices=[]
            for resolved in range(max(1,line_no-1),min(len(lines),line_no+1)+1):
                quoted=v3.evidence_anchor(page,resolved,quote)
                if not quoted:
                    continue
                local=[o for o in options if o['page']==page_no and o['value']==token and resolved in {o['line'],o['label_line']}]
                for option in local:
                    if identity and resolved != line_no and line_no <= len(lines):
                        declared_party=party_at_label(lines,line_no-1,len(lines[line_no-1]),document_type)
                        if declared_party!=option['party']:
                            continue
                    # A label-only quote may anchor an adjacent value. Both native
                    # text locations must exist; no registered amount is substituted.
                    has_value=field=='amount_scope' or in_quote(field,token,quote)
                    has_label=resolved==option['label_line'] and option['label'] in quote
                    if not has_value and not has_label:
                        continue
                    value_quote=lines[option['line']-1]
                    linked=v3.evidence_anchor(page,option['line'],value_quote)
                    label_anchor=v3.evidence_anchor(page,option['label_line'],lines[option['label_line']-1])
                    if linked and label_anchor:
                        linked['label_anchor']=label_anchor
                        choices.append((resolved,quoted,option,linked))
            exact=[c for c in choices if c[0]==line_no]
            selected=exact if exact else choices
            if len({(c[2]['line'],c[2]['label_line'],c[2]['party']) for c in selected})==1:
                resolved,quoted,option,anchor=selected[0]
                matches=[option]
                anchor.update(label=option['label'],label_line=option['label_line'],party=option['party'],proposal_anchor=quoted)
                if resolved!=line_no:
                    warnings.append('LINE_OFFSET_RESOLVED')
                if option['line']!=resolved:
                    warnings.append('ADJACENT_LABEL_VALUE_VERIFIED')
        if anchor is None:
            reasons.append('EVIDENCE_NOT_FOUND')
            if structural:
                reasons.append('DOCX_LOCATION_UNVERIFIED')
        if not matches:
            reasons.append('FIELD_LABEL_OR_VALUE_MISMATCH')
            if field!='amount_scope' and token is not None and not in_quote(field,token,quote if isinstance(quote,str) else ''):
                reasons.append('VALUE_NOT_IN_QUOTE')
        if identity and matches and matches[0]['party']!='supplier':
            reasons.append('WRONG_PARTY')
        if len(distinct)>1:
            reasons.append('AMBIGUOUS')
        if field=='business_registration_no' and not v3.checksum_valid(token):
            reasons.append('INVALID_CHECKSUM')
        if field=='amount_scope' and token not in {'FULL','PARTIAL'}:
            reasons.append('INVALID_FORMAT')
        numbers={key:{o['value'] for o in candidates(pages,key,document_type)} for key in MONEY_FIELDS}
        if all(len(values)==1 for values in numbers.values()):
            supply,tax,total=(Decimal(next(iter(numbers[key]))) for key in ('supply_amount','tax_amount','total_amount'))
            if supply+tax!=total:
                warnings.append('SOURCE_ARITHMETIC_MISMATCH')
    return {'field':field,'proposal':proposal,'accepted':not reasons,'reasons':list(dict.fromkeys(reasons)),
            'warnings':warnings,'anchor':anchor,'human_confirmed':False}
