"""Bounded original-source comparisons; never impersonate human confirmation.

Repeat identity and full-payment monetary fields require visible native-PDF
evidence or hash-bound raster OCR/row-crop evidence built during ingestion.
Unverified scans, hidden/covered text and ambiguous parties keep human review.
No OCR/model/network call at this gate.
"""
import ctypes
import math
import re
from functools import lru_cache

from ..ai.grounding import candidates, LABELS, MONEY_TOKEN, BUYER, SUPPLIER
from ..ai.pdf_runtime import (PDFIUM_LOCK, open_pdf, open_page, open_textpage,
                              page_count, page_text, page_size, matching_text_rectangles)
from ..validation.engine import normalize_party_name
from ..validation.financial import money

POLICY = 'contract-risk-review-v3'
KINDS = {'estimate', 'business_registration', 'tax_invoice', 'bank_account', 'inspection_confirmation'}
NUMBER = re.compile(r'(?<!\d)\d{3}[ -]*\d{2}[ -]*\d{5}(?!\d)')


def number(value):
    return re.sub(r'[\s-]', '', str(value or ''))


def _scan_line(text):
    """Only reconnect known OCR field labels; never repair a value."""
    head,sep,tail=text.partition(':')
    if not sep:head,sep,tail=text.partition('：')
    if not sep:
        match=re.match(r'^\s*([가-힣\s]+)([.。•·](?=\s)|=)\s*(.*)$',text)
        if match:head,sep,tail=match.groups()
    compact=re.sub(r'\s+','',head)
    labels={'상호','업체명','예금주','사업자등록번호','사업자번호','등록번호',
            '공급가액','공급금액','부가가치세','부가세','세액','합계금액','총금액','총액','합계'}
    if sep and compact in labels:return compact+': '+tail.strip()
    if not sep and compact in {'공급자','공급받는자','매출자','매입자','수급인','발주자'}:return compact
    return text.strip()


def _scan_identity(pages,kind):
    nums=candidates(pages,'business_registration_no',kind)
    names=candidates(pages,'company_name',kind)
    names=[c for c in names if re.match(r'\s*(?:'+LABELS['company_name']+r')',pages[c['page']-1]['text'].splitlines()[c['label_line']-1])]
    labels=sum(len(re.findall(LABELS['business_registration_no'],p['text'])) for p in pages)
    if labels!=len(nums) or not nums or not names or any(c['party']=='ambiguous' for c in nums+names):return None
    if {number(m.group()) for p in pages for m in NUMBER.finditer(p['text'])}!={number(c['value']) for c in nums}:return None
    supplier=[c for c in nums if c['party']=='supplier'];owner=[c for c in names if c['party']=='supplier']
    if not supplier and not any(c['party']=='buyer' for c in nums+names):supplier,owner=nums,names
    if any(c['party']=='unknown' for c in nums+names) and any(c['party']=='buyer' for c in nums+names):return None
    if len({number(c['value']) for c in supplier})!=1 or len({normalize_party_name(c['value']) for c in owner})!=1:return None
    if not re.fullmatch(r'\d{10}',number(supplier[0]['value'])):return None
    identity={'number':number(supplier[0]['value']),'name':normalize_party_name(owner[0]['value']),'financial':{},'locations':{}}
    selected={'company_name':owner[0],'business_registration_no':supplier[0]}
    if kind in {'estimate','tax_invoice'}:
        for field in ('total_amount','supply_amount','tax_amount'):
            found=[c for c in candidates(pages,field,kind) if c['line']==c['label_line']]
            matching=[c for c in found if re.match(r'\s*(?:'+LABELS[field]+r')',pages[c['page']-1]['text'].splitlines()[c['line']-1]) and
                      re.search(r'(?:[₩￦]\s*'+MONEY_TOKEN+r'|'+MONEY_TOKEN+r'\s*원(?:\s|$|[.,(]))',pages[c['page']-1]['text'].splitlines()[c['line']-1])]
            labels=sum(bool(re.match(r'\s*(?:'+LABELS[field]+r')',line)) for p in pages for line in p['text'].splitlines())
            if matching and len(matching)==labels and len({c['value'] for c in matching})==1:
                identity['financial'][field]=matching[0]['value'];selected[field]=matching[0]
    for field,c in selected.items():identity['locations'][field]={'page':c['page'],'line':c['line']}
    identity['values']={field:c['value'] for field,c in selected.items()}
    identity.update(page=supplier[0]['page'],line=supplier[0]['line'])
    return identity,selected


def build_scan_review(path,source_sha256,kind):
    """At ingestion only: full raster OCR + original row-crop agreement.

    Uses the already-installed Windows OCR. This is bounded source evidence,
    not a calibrated confidence or independent OCR accuracy guarantee.
    Never run this from a GET/submission gate and never rewrite extracted values.
    """
    from pathlib import Path
    from PIL import Image,ImageStat
    from ..ai.preprocessor import _safe_winocr_recognize,prepare_winocr_image,_to_pil_image
    from .evidence_geometry_service import normalized_box,union
    from ..ai.pdf_runtime import render_page_image
    suffix=Path(path).suffix.lower()
    if kind not in KINDS or suffix not in {'.pdf','.png','.jpg','.jpeg','.bmp','.webp'}:return None
    images=[];targets=[]
    result={'policy':POLICY,'source_sha256':source_sha256,'kind':kind,'method':'RASTER_OCR_ROW_CROP','identity':None,'verified_fields':[],'reason':'SCAN_SOURCE_UNVERIFIED'}
    try:
        if suffix=='.pdf':
            with open_pdf(path) as pdf:
                if not 0<page_count(pdf)<=3:return result
                for i in range(page_count(pdf)):
                    with open_page(pdf,i) as page,open_textpage(page) as text:
                        if page_text(text).strip():return None  # native/mixed PDF stays on native policy
                        images.append(render_page_image(page,2))
        else:
            image=_to_pil_image(path)
            if image is None:return result
            images.append(image)
        pages=[];rows={}
        for pi,image in enumerate(images,1):
            with image.convert('L') as gray:
                if max(ImageStat.Stat(gray).stddev)<12:return result
            target=prepare_winocr_image(image);targets.append(target)
            ocr=_safe_winocr_recognize(target,lang='ko') or {};lines=[l for l in ocr.get('lines',[]) if l.get('text','').strip()]
            if not lines or sum(len(l['text']) for l in lines)>50_000:return result
            pages.append({'page':pi,'text':'\n'.join(_scan_line(l['text']) for l in lines)})
            rows.update({(pi,li):l for li,l in enumerate(lines,1)})
        parsed=_scan_identity(pages,kind)
        if not parsed:result['reason']='SCAN_PARTY_OR_LAYOUT_AMBIGUOUS';return result
        identity,selected=parsed
        # Role labels must agree too; an unreadable supplier heading cannot be guessed.
        locations={(c['page'],c['line']) for c in selected.values()}
        locations.update((p['page'],li) for p in pages for li,line in enumerate(p['text'].splitlines(),1) if BUYER.search(line) or SUPPLIER.search(line))
        verified={};boxes={}
        for page,line in locations:
            row=rows[(page,line)];words=row.get('words') or [];target=targets[page-1]
            coords=[]
            if not words or re.sub(r'\s+','',row['text'])!=re.sub(r'\s+','',' '.join(w.get('text','') for w in words)):continue
            for word in words:
                rect=word.get('bounding_rect') or {}
                if not all(k in rect for k in ('x','y','width','height')):coords=[];break
                box=normalized_box(page,tuple(rect[k] for k in ('x','y','width','height')),*target.size)
                if box is None:coords=[];break
                coords.append(box)
            box=union(coords)
            if not box:continue
            x,y=box['x']*target.width,box['y']*target.height
            right,bottom=x+box['width']*target.width,y+box['height']*target.height
            # Preserve the original horizontal row context instead of enlarging
            # a tight number crop; table columns in the same band must also agree.
            with target.crop((0,max(0,int(y)-12),target.width,min(target.height,math.ceil(bottom)+12))) as crop:
                with crop.convert('L') as gray:
                    if max(ImageStat.Stat(gray).stddev)<12:continue
                # Second read uses the original raster row at a different scale.
                with Image.new('RGB',(max(500,crop.width+40),max(140,crop.height+40)),'white') as padded:
                    padded.paste(crop,(20,20));resized=prepare_winocr_image(padded)
                    try:second=_safe_winocr_recognize(resized,lang='ko') or {}
                    finally:
                        if resized is not padded:resized.close()
            second_text=' '.join(l.get('text','') for l in second.get('lines',[])) or second.get('text','')
            if re.sub(r'\s+','',_scan_line(second_text))==re.sub(r'\s+','',_scan_line(row['text'])):verified[(page,line)]=True;boxes[(page,line)]=box
        role_locations={(p['page'],li) for p in pages for li,line in enumerate(p['text'].splitlines(),1) if BUYER.search(line) or SUPPLIER.search(line)}
        if not role_locations.issubset(verified):result['reason']='SCAN_PARTY_CROP_DISAGREES';return result
        for field,c in selected.items():
            loc=(c['page'],c['line'])
            if loc in verified:
                result['verified_fields'].append(field);identity['locations'][field]['bbox']=boxes[loc]
        result.update(identity=identity,reason='SCAN_FIELD_CROP_DISAGREES' if len(result['verified_fields'])!=len(selected) else None)
        return result
    except Exception:
        return result
    finally:
        for image in targets:
            if all(image is not original for original in images):image.close()
        for image in images:image.close()


def overlaps(a, b, padding=1):
    return a[0] < b[2]+padding and a[2] > b[0]-padding and a[1] < b[3]+padding and a[3] > b[1]-padding


def bounds(raw, obj):
    box = [ctypes.c_float() for _ in range(4)]
    if not raw.FPDFPageObj_GetBounds(obj, *(ctypes.byref(x) for x in box)):
        raise ValueError('unavailable object bounds')
    values = tuple(x.value for x in box)
    if not all(math.isfinite(x) for x in values):
        raise ValueError('invalid object bounds')
    return values


def visible_identity(page, textpage, tokens):
    """Only visible text and non-overlapping straight table/decorative paths.

    Paths are inspected in page coordinates, including their closing edges and
    stroke width. A filled cover, strike-through, clipping, image, Form, shading
    or annotation prevents exemption. Even unrelated hidden text fails closed.
    """
    import pypdfium2.raw as raw
    protected=[]
    for token in set(tokens):
        token_boxes=matching_text_rectangles(textpage,token)
        if not token_boxes:
            return False
        protected.extend((box,token) for box in token_boxes)
    boxes=[box for box,_ in protected]
    if not boxes or raw.FPDFPage_GetAnnotCount(page) != 0:
        return False
    width, height = page_size(page)
    count = raw.FPDFPage_CountObjects(page)
    if not 0 < count <= 10_000:
        return False
    for index in range(count):
        obj = raw.FPDFPage_GetObject(page, index)
        kind = raw.FPDFPageObj_GetType(obj)
        clip = raw.FPDFPageObj_GetClipPath(obj)
        if clip and raw.FPDFClipPath_CountPaths(clip) > 0:
            return False
        if kind == raw.FPDF_PAGEOBJ_TEXT:
            if raw.FPDFTextObj_GetTextRenderMode(obj) != 0:
                return False
            channels = [ctypes.c_uint() for _ in range(4)]
            if not raw.FPDFPageObj_GetFillColor(obj, *(ctypes.byref(c) for c in channels)):
                return False
            if channels[3].value != 255 or all(c.value > 235 for c in channels[:3]):
                return False
            left, bottom, right, top = bounds(raw, obj)
            if not 0 <= left < right <= width or not 0 <= bottom < top <= height:
                return False
            if any(overlaps((left,bottom,right,top),b,0) for b in boxes):
                size=raw.FPDFTextObj_GetText(obj,textpage,None,0)
                if not 0 < size <= 100_000:
                    return False
                buffer=(ctypes.c_ushort*((size+1)//2))()
                if raw.FPDFTextObj_GetText(obj,textpage,buffer,size)!=size:
                    return False
                text=bytes(buffer).decode('utf-16-le').rstrip('\x00').strip()
                if not text or any(token not in text for box,token in protected if overlaps((left,bottom,right,top),box,0)):
                    return False  # another text object covers the protected glyphs
        elif kind == raw.FPDF_PAGEOBJ_PATH:
            fill, stroke = ctypes.c_int(), ctypes.c_int()
            if not raw.FPDFPath_GetDrawMode(obj, ctypes.byref(fill), ctypes.byref(stroke)):
                return False
            if fill.value != raw.FPDF_FILLMODE_NONE and any(overlaps(bounds(raw,obj), b) for b in boxes):
                return False
            if not stroke.value:
                continue
            matrix = raw.FS_MATRIX()
            linewidth = ctypes.c_float()
            if not raw.FPDFPageObj_GetMatrix(obj, ctypes.byref(matrix)) or not raw.FPDFPageObj_GetStrokeWidth(obj, ctypes.byref(linewidth)):
                return False
            margin = max(1, abs(linewidth.value)*max(math.hypot(matrix.a,matrix.b),math.hypot(matrix.c,matrix.d))/2)
            previous = first = None
            segments = raw.FPDFPath_CountSegments(obj)
            if not 0 < segments <= 1000:
                return False
            for si in range(segments):
                segment = raw.FPDFPath_GetPathSegment(obj, si)
                stype = raw.FPDFPathSegment_GetType(segment)
                if stype not in {raw.FPDF_SEGMENT_MOVETO,raw.FPDF_SEGMENT_LINETO}:
                    return False
                x,y = ctypes.c_float(),ctypes.c_float()
                if not raw.FPDFPathSegment_GetPoint(segment,ctypes.byref(x),ctypes.byref(y)):
                    return False
                point=(matrix.a*x.value+matrix.c*y.value+matrix.e,matrix.b*x.value+matrix.d*y.value+matrix.f)
                if not all(math.isfinite(v) for v in point):
                    return False
                def edge(a,b):
                    return (min(a[0],b[0])-margin,min(a[1],b[1])-margin,max(a[0],b[0])+margin,max(a[1],b[1])+margin)
                if stype == raw.FPDF_SEGMENT_MOVETO:
                    first=point
                elif previous is None or any(overlaps(edge(previous,point),b,0) for b in boxes):
                    return False
                if raw.FPDFPathSegment_GetClose(segment) and (first is None or any(overlaps(edge(point,first),b,0) for b in boxes)):
                    return False
                previous=point
        else:
            return False
    return True


@lru_cache(maxsize=64)
def native_identity(path, source_sha256, kind):
    """Caller has verified SHA-256. Cache keys bind to immutable source bytes."""
    if kind not in KINDS or not path.lower().endswith('.pdf'):
        return None
    try:
        pages=[]
        from pypdf import PdfReader
        catalog=PdfReader(path).trailer['/Root']
        if '/OCProperties' in catalog or '/AcroForm' in catalog:
            return None  # text in optional layers/forms may not be what users see
        with open_pdf(path) as pdf:
            if not 0 < page_count(pdf) <= 10:
                return None
            for index in range(page_count(pdf)):
                with open_page(pdf,index) as page, open_textpage(page) as textpage:
                    text=page_text(textpage)
                    if not text.strip() or len(text)>50_000:
                        return None
                    pages.append({'page':index+1,'text':text})
            nums=candidates(pages,'business_registration_no',kind)
            names=candidates(pages,'company_name',kind)
            labels=sum(len(re.findall(LABELS['business_registration_no'],p['text'])) for p in pages)
            if labels != len(nums):
                return None  # unreadable/partial extra identifiers cannot be ignored
            # A prose sentence mentioning "상호 / 인명" is not an identity field.
            names=[c for c in names if re.match(r'\s*(?:'+LABELS['company_name']+r')',
                    pages[c['page']-1]['text'].splitlines()[c['label_line']-1])]
            if not nums or not names or any(c['party']=='ambiguous' for c in nums+names):
                return None
            # Unlabelled second numbers/unknown parties cannot be silently ignored.
            all_nums={number(m.group()) for p in pages for m in NUMBER.finditer(p['text'])}
            if all_nums!={number(c['value']) for c in nums}:
                return None
            supplier=[c for c in nums if c['party']=='supplier']
            owner=[c for c in names if c['party']=='supplier']
            if not supplier and not any(c['party']=='buyer' for c in nums+names):
                supplier,owner=nums,names  # a single-party estimate with no role heading
            if any(c['party']=='unknown' for c in nums+names) and any(c['party']=='buyer' for c in nums+names):
                return None
            unique_nums={number(c['value']) for c in supplier}
            unique_names={normalize_party_name(c['value']) for c in owner}
            if len(unique_nums)!=1 or len(unique_names)!=1:
                return None
            found=next(iter(unique_nums))
            if not re.fullmatch(r'\d{10}',found) or not next(iter(unique_names)):
                return None
            financial={}
            monetary=[]
            locations={'company_name':{'page':owner[0]['page'],'line':owner[0]['line']},
                       'business_registration_no':{'page':supplier[0]['page'],'line':supplier[0]['line']}}
            if kind in {'estimate','tax_invoice'}:
                for field in ('total_amount','supply_amount','tax_amount'):
                    found_money=candidates(pages,field,kind)
                    found_money=[c for c in found_money if re.match(r'\s*(?:'+LABELS[field]+r')',
                        pages[c['page']-1]['text'].splitlines()[c['label_line']-1])]
                    def monetary_token(c):
                        line=pages[c['page']-1]['text'].splitlines()[c['line']-1]
                        tail=line.partition(c['label'])[2] if c['line']==c['label_line'] else line
                        tail=re.sub(r'^\s*(?:[:：=]|[.。•·](?=\s))?\s*','',tail)
                        match=re.match(r'(?:[₩￦]|금)?\s*('+MONEY_TOKEN+r')',tail)
                        if not match or not (tail.startswith(('₩','￦')) or re.match(r'\s*원(?:$|\s|[.,(])',tail[match.end():])):
                            return None
                        return match.group(1)
                    found_money=[{**c,'raw_token':monetary_token(c)} for c in found_money]
                    found_money=[c for c in found_money if c['raw_token']]
                    amounts={c['value'] for c in found_money}
                    labels=sum(bool(re.match(r'\s*(?:'+LABELS[field]+r')',line)) for p in pages for line in p['text'].splitlines())
                    if len(amounts)==1 and len(found_money)==labels:
                        financial[field]=next(iter(amounts))
                        locations[field]={'page':found_money[0]['page'],'line':found_money[0]['line']}
                        monetary.extend(found_money)
            # Verify the actual glyphs of all parties, not just the desired number.
            for index,p in enumerate(pages):
                lines=p['text'].splitlines()
                tokens=[]
                for c in nums+names+monetary:
                    if c['page']!=index+1:
                        continue
                    line=lines[c['line']-1]
                    tail=line.partition(c['label'])[2] if c['line']==c['label_line'] else line
                    tail=re.sub(r'^\s*(?:[:：=]|[.。•·](?=\s))?\s*','',tail)
                    if c in monetary:
                        token=c['raw_token']
                    elif c in nums:
                        match=re.match(r'\d{3}[\s-]*\d{2}[\s-]*\d{5}(?!\d)',tail)
                        if not match:
                            return None
                        token=match.group()
                    else:
                        token=tail.strip()
                    tokens.extend([c['label'],token])
                tokens.extend(m.group() for pattern in (BUYER,SUPPLIER) for m in pattern.finditer(p['text']))
                if not tokens:
                    return None
                with open_page(pdf,index) as page, open_textpage(page) as textpage, PDFIUM_LOCK:
                    if not visible_identity(page,textpage,tokens):
                        return None
            return {'number':found,'name':next(iter(unique_names)),
                    'page':supplier[0]['page'],'line':supplier[0]['line'],'financial':financial,'locations':locations}
    except Exception:
        return None


def automatic_field_review(doc, field, values, stored, checks, path, source_sha256, anchor, decisions, human_fields=()):
    kind=getattr(doc.document_type,'value',doc.document_type)
    ai=stored.get('ai_review') or {}
    if (kind not in KINDS or not anchor or field in decisions or any(d.get('kind')!='NO_ISSUE' for d in decisions.values())
            or ai.get('manual_review_required') and not ai.get('targets') or field in (ai.get('targets') or [])):
        return None
    related=[c for c in checks if c.field==str(doc.document_id)]
    if any(c.rule_id in {'BUSINESS_NO_MATCH','DOCUMENT_TYPE','ORIGINAL_FILE','DOCUMENT_PROCESSING'} and c.status!='PASS' for c in related):
        return None
    identity=native_identity(str(path),source_sha256,kind)
    method='PDF_NATIVE_TEXT'
    if not identity:
        scan=(stored.get('extraction_metadata') or {}).get('automatic_source_review') or {}
        key='total_amount' if field=='amount' else field
        verified=set(scan.get('verified_fields') or [])
        required={key}
        if kind=='tax_invoice' and field not in {'company_name','business_registration_no'}:required|={'total_amount','supply_amount','tax_amount'}
        if (scan.get('policy')!=POLICY or scan.get('source_sha256')!=source_sha256 or scan.get('kind')!=kind
                or scan.get('method')!='RASTER_OCR_ROW_CROP' or not required.issubset(scan.get('verified_fields') or [])):
            return None
        identity=scan.get('identity');method='RASTER_OCR_ROW_CROP'
        if not identity:return None
        identity=dict(identity)
        for key,identity_key,normalize in [('company_name','name',normalize_party_name),('business_registration_no','number',number)]:
            if key not in verified:
                if key not in human_fields or normalize(values.get(key))!=anchor[identity_key]:return None
                identity[identity_key]=normalize(values[key])  # current source-bound human identity, never a fabricated proof
    if not identity or (identity['number'],identity['name'])!=(number(values.get('business_registration_no')),normalize_party_name(values.get('company_name'))):
        return None
    if (identity['number'],identity['name'])!=(anchor['number'],anchor['name']):
        return None
    reason='계약 거래처와 원본의 공급자 상호·번호 일치'
    if field not in {'company_name','business_registration_no'}:
        if kind not in {'estimate','tax_invoice'} or field not in {'total_amount','amount','supply_amount','tax_amount'}:
            return None
        if anchor.get('total') is None or anchor.get('payment_mode')!='FULL':
            return None
        # Numeric source/contract agreement is separate from claim meaning.
        # UNKNOWN remains a mandatory scope input in the gate; PARTIAL cannot
        # use this full-contract monetary exemption.
        if kind=='tax_invoice' and values.get('amount_scope') not in {'FULL','UNKNOWN'}:
            return None
        if not any(c.rule_id=='AMOUNT_MATCH_'+kind.upper() and c.status=='PASS' for c in related):
            return None
        if any(c.rule_id.startswith('AMOUNT_') and c.status!='PASS' for c in related):
            return None
        financial=identity['financial']
        total=money(financial.get('total_amount'))
        key='total_amount' if field=='amount' else field
        if total!=anchor['total'] or key not in financial or money(financial[key])!=money(values.get(field)):
            return None
        if kind=='tax_invoice':
            supply,tax=money(financial.get('supply_amount')),money(financial.get('tax_amount'))
            if supply is None or tax is None or supply+tax!=total:
                return None
            if any(money(financial.get(k))!=money(values.get(k)) for k in ('supply_amount','tax_amount','total_amount')):
                return None
        reason='원본 금액·공급자·산술과 계약 합계가 일치'
    return {'document_id':doc.document_id,'document_type':kind,'field':field,'source_sha256':source_sha256,
            'anchor_document_id':anchor['document_id'],'anchor_confirmed':bool(anchor.get('confirmed')),'policy':POLICY,
            'page':identity['locations']['total_amount' if field=='amount' else field]['page'],
            'line':identity['locations']['total_amount' if field=='amount' else field]['line'],
            'source_method':method,'bbox':identity['locations']['total_amount' if field=='amount' else field].get('bbox'),
            'reason':reason}


def automatic_business_review(doc,values,stored,checks,path,source_sha256,anchor,decisions):
    return automatic_field_review(doc,'business_registration_no',values,stored,checks,path,source_sha256,anchor,decisions)
