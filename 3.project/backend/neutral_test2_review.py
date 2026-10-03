"""Twenty neutral questions; preserve the original answers, labels and predictions."""
import hashlib
import html
import json
import random
import re
import unicodedata
from pathlib import Path

SEED = 20261003
FORMAT = 'test2-neutral-recheck-v1'
UNCERTAIN = ['UNSURE', '판단하기 어려움']
TYPES = [['contract','계약서'],['estimate','견적서'],['business_registration','사업자등록증'],
         ['bankbook','통장사본'],['tax_invoice','세금계산서'],['inspection_confirmation','검수확인서'],['unknown','다른 종류 / 알 수 없음']]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_page(path):
    return json.loads(Path(path).read_text('utf-8').split('const DATA = ',1)[1].split(';\nconst STORE',1)[0])


def question(item):
    label = item['label'].split('/')[0]
    result = {k:item[k] for k in ('id','cid','doc','sheet','row','kind')}
    result.update(input_type=None, uses_registration=False, hint='원문을 보고 답해주세요. 이전 답이나 정답 초안은 표시하지 않습니다.')
    if label in ('supply_amount','total_amount','company_name'):
        name = {'supply_amount':'공급가액','total_amount':'합계금액','company_name':'계약상대자 상호'}[label]
        result.update(prompt=f'이 문서에서 {name}을 어떻게 읽었나요?',
            options=[['VALUE','읽은 값을 직접 입력'],['ABSENT','해당 항목이 없음'],['REVIEW','항목이 있지만 읽거나 뜻을 확정할 수 없음']],
            input_type='text' if label=='company_name' else 'amount', input_label=name,
            hint='다른 서류의 값이나 계산으로 채우지 말고, 이 원문에서 읽은 값을 적어주세요.')
    elif label=='document_type':
        result.update(prompt='이 문서는 어떤 종류인가요?',options=TYPES)
    elif label=='amount_scope':
        result.update(prompt='이 문서에 적힌 금액의 적용 범위는 무엇인가요?', options=[
            ['FULL','계약 전체에 해당'],['PARTIAL','선금·잔금 등 일부에 해당'],['REVIEW','금액은 있지만 범위를 확정할 수 없음'],['ABSENT','금액 항목이 없음']],
            hint='문서가 나타내는 거래와 금액 범위를 살펴보세요. 전체 거래, 일부 지급, 범위 불명, 금액 없음 중 고르세요.')
    elif label=='BUSINESS_STATUS':
        result.update(prompt='제공된 자료로 이 업체가 실제 영업 중인지 판단할 수 있나요?',
            options=[['VERIFIABLE','판단할 수 있음'],['UNVERIFIABLE','이 자료만으로 판단할 수 없음']],
            hint='이번 평가에는 국세청 조회 결과가 제공되지 않았습니다.')
    elif label=='DOCUMENT_PROCESSING':
        result.update(prompt='이 문서의 글자를 어느 정도 읽을 수 있나요?',
            options=[['READABLE','읽을 수 있음'],['PARTLY','일부만 읽을 수 있음'],['UNREADABLE','읽을 수 없음']])
    elif label=='DOCUMENT_TYPE':
        result.update(prompt='제목과 내용으로 이 문서의 종류를 구분할 수 있나요?',
            options=[['IDENTIFIABLE','구분할 수 있음'],['UNIDENTIFIABLE','구분할 수 없음']])
    elif label=='missing_types':
        result.update(prompt='이 계약에 필요한 6종 서류가 제출되어 있나요?',
            options=[['ALL_PRESENT','6종 모두 있음'],['MISSING','누락된 종류가 있음']],
            hint='계약서·견적서·사업자등록증·통장사본·세금계산서·검수확인서를 문서 버튼으로 각각 열어보세요.')
    elif label=='AMOUNT_BASIS':
        result.update(prompt='등록 계약의 금액 기준은 무엇인가요?',options=[
            ['TOTAL','세액을 포함한 합계 기준'],['SUPPLY','세액을 제외한 공급가액 기준'],['UNCLEAR','기준이 명시되지 않음']],uses_registration=True)
    elif label=='AMOUNT_MATCH_TAX_INVOICE':
        result.update(prompt='이 세금계산서의 합계금액과 등록 계약의 비교 금액은 어떤 관계인가요?',
            options=[['SAME','같음'],['DIFFERENT','다름'],['REVIEW','확인할 수 없음'],['NA','이 비교의 대상이 아님']],uses_registration=True)
    elif label=='REQUIRED_DOCUMENTS' and item['label'].endswith('/inspection_confirmation'):
        result.update(prompt='이 계약에 납품 검수확인서가 제출되어 있나요?',options=[['PRESENT','있음'],['MISSING','없음']])
    else:
        raise ValueError(f'UNMAPPED_QUESTION: {item["id"]}')
    result['options'] = [*result['options'],UNCERTAIN]
    return result


def baseline(item):
    """Match the assertion the person actually saw, not an unasked N/A status."""
    if item['kind']=='field':
        state,value = item['excel'].split(' / ',1)
        if item['label']=='document_type':
            return {'choice':value,'value':None,'construct':'DIRECT_LABEL'}
        if item['label']=='amount_scope' and state=='VALUE':
            return {'choice':value,'value':None,'construct':'DIRECT_LABEL'}
        return {'choice':state,'value':value if state=='VALUE' else None,'construct':'DIRECT_LABEL'}
    label = item['label'].split('/')[0]
    choices = {'BUSINESS_STATUS':'UNVERIFIABLE','DOCUMENT_PROCESSING':'READABLE',
        'DOCUMENT_TYPE':'IDENTIFIABLE','missing_types':'ALL_PRESENT','AMOUNT_BASIS':'TOTAL',
        'AMOUNT_MATCH_TAX_INVOICE':'SAME','REQUIRED_DOCUMENTS':'PRESENT'}
    return {'choice':choices[label],'value':None,
            'construct':'SOURCE_FACT_ONLY' if item['excel']=='N/A' else 'DIRECT_LABEL'}


def prepare(project):
    project = Path(project)
    original = project/'eval/human_review_page_test2/index.html'
    human = project/'eval/human_reviews/test2/human_review_result_test2_이창헌.json'
    page,answers = read_page(original),json.loads(human.read_text('utf-8'))
    population = sorted(page['items'],key=lambda x:x['id'])
    if len(population)!=81 or len({i['id'] for i in population})!=81:
        raise ValueError('EXPECTED_81_UNIQUE_ORIGINAL_QUESTIONS')
    selected = random.Random(SEED).sample(population,20)
    answer_by_id = {i['id']:i for i in answers['items']}
    if any(answer_by_id[q['id']]['decision']!='확인' for q in selected):
        raise ValueError('BASELINE_MAPPING_NEEDS_MANUAL_ADJUDICATION')
    for q in selected:
        claim=q['q'].split('<div class="claim">',1)[1].split('</div>',1)[0]
        claim=html.unescape(re.sub('<[^>]+>','',claim))
        if claim not in answer_by_id[q['id']]['reason']:
            raise ValueError('QUESTION_DIFFERS_FROM_ORIGINAL_RECORDED_ASSERTION')
    manifest = {'format':FORMAT,'seed':SEED,'method':'Python random.Random(seed).sample, sorted by original id, without replacement',
        'population_count':81,'sample_count':20,'original_page_sha256':digest(original),
        'original_answers_sha256':digest(human),'original_workbook_sha256':page['source_xlsx_sha256'],
        'population_ids':[q['id'] for q in population],'selected_ids':[q['id'] for q in selected]}
    selection_id = hashlib.sha256(json.dumps(manifest,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    manifest['selection_id'] = selection_id
    public = {'format':FORMAT,'selection_id':selection_id,'items':[question(q) for q in selected],'cases':{}}
    for cid in sorted({q['cid'] for q in selected}):
        case = page['cases'][cid]
        public['cases'][cid] = {k:case[k] for k in ('case','vendor','bno','basis','pay')}
        public['cases'][cid]['docs'] = [{k:d[k] for k in ('id','src','name')} | {
            'views':['../human_review_page_test2/'+v for v in d['views']]} for d in case['docs']]
    private = {'format':FORMAT,'selection_id':selection_id,'items':[
        {'id':q['id'],**baseline(q),'original_question':q['q'],'original_decision':answer_by_id[q['id']]['decision']} for q in selected]}
    return public,manifest,private


def write_new_or_identical(path,contents):
    path = Path(path)
    if path.exists() and path.read_bytes()!=contents.encode('utf-8'):
        raise ValueError(f'REFUSING_TO_OVERWRITE_EXISTING_RECHECK_FILE: {path}')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(contents.encode('utf-8'))


def build(project):
    project = Path(project)
    public,manifest,private = prepare(project)
    template = (project/'backend/templates/neutral_test2_review.html').read_text('utf-8')
    # Reuse the original page's layout; do not alter it or the application frontend.
    source = (project/'eval/human_review_page_test2/index.html').read_text('utf-8')
    css = source.split('<style>',1)[1].split('</style>',1)[0]
    html = template.replace('/* ORIGINAL_STYLE */',css).replace('__PUBLIC_DATA__',json.dumps(public,ensure_ascii=False).replace('</','<\\/'))
    folder = project/'eval/human_review_page_test2_neutral'
    write_new_or_identical(folder/'index.html',html)
    for name,data in (('sample_manifest.json',manifest),('comparison_baseline.json',private)):
        write_new_or_identical(folder/name,json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    return public


def normalize(value,kind):
    value = unicodedata.normalize('NFKC',str(value)).strip()
    if kind=='amount':
        value = value.replace(',','').replace('원','').replace('₩','').strip()
        if not re.fullmatch(r'\d+',value):
            raise ValueError('AMOUNT_MUST_BE_WHOLE_WON')
        return str(int(value))
    return re.sub(r'\s+','',value)


def compare(project,result):
    public,manifest,private = prepare(project)
    if result.get('format')!=FORMAT or result.get('selection_id')!=public['selection_id']:
        raise ValueError('WRONG_RECHECK_VERSION')
    if not str(result.get('reviewer','')).strip():
        raise ValueError('REVIEWER_REQUIRED')
    items = result.get('responses',[])
    ids = [q.get('id') for q in items]
    if len(ids)!=len(set(ids)) or not set(ids)<=set(manifest['selected_ids']):
        raise ValueError('DUPLICATE_OR_UNKNOWN_ANSWER')
    submitted = {q['id']:q for q in items}
    old = {q['id']:q for q in private['items']}
    rows=[]
    for q in public['items']:
        response = submitted.get(q['id'])
        status = 'UNANSWERED'
        if response:
            choice = response.get('choice')
            if choice not in {o[0] for o in q['options']} or not response.get('reviewed_at'):
                raise ValueError('INVALID_RESPONSE')
            value = response.get('value')
            if choice=='UNSURE':
                status='UNCERTAIN'
            else:
                same = choice==old[q['id']]['choice']
                if choice=='VALUE':
                    if not str(value or '').strip() and value!=0:
                        raise ValueError('VALUE_REQUIRED')
                    normalized = normalize(value,q['input_type'])
                    same = same and normalized==normalize(old[q['id']]['value'],q['input_type'])
                status='AGREE' if same else 'DISAGREE'
        rows.append({'id':q['id'],'construct':old[q['id']]['construct'],'status':status,'response':response,'previous':old[q['id']]})
    counts={s:sum(r['status']==s for r in rows) for s in ('AGREE','DISAGREE','UNCERTAIN','UNANSWERED')}
    comparable=counts['AGREE']+counts['DISAGREE']
    return {'format':FORMAT+'-agreement','selection_id':public['selection_id'],'reviewer':result['reviewer'],
        'counts':counts,'total_selected':20,'agreement_among_comparable':counts['AGREE']/comparable if comparable else None,
        'agreement_over_all_selected':counts['AGREE']/20,'comparable_count':comparable,
        'complete':counts['UNANSWERED']==0,'labels_or_original_answers_changed':False,
        'limitation':'Same reviewer and repeated documents; descriptive agreement, not causal wording effect or label accuracy.',
        'by_construct':{c:{s:sum(r['construct']==c and r['status']==s for r in rows) for s in counts} for c in sorted({r['construct'] for r in rows})},
        'items':rows}
