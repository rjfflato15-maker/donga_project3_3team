"""Describe saved test2 predictions only: no model, guard, OCR, rules or DB runs."""
import csv
import importlib.util
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import NormalDist

from backend.prediction_artifacts import verify_package, load_checkpoint, file_hash

MODES = {'rule':'규칙만', 'llm':'LLM만', 'hybrid_unguarded':'규칙+LLM, 가드 없음', 'hybrid_guarded':'규칙+LLM, 가드 v4'}
CRITICAL = {'business_registration_no', 'supply_amount', 'tax_amount', 'total_amount', 'account_number'}
SOURCES = {'HUMAN_DIRECT_LABEL':'사람 직접 라벨 확인', 'HUMAN_OBSERVATION_ADJUDICATED':'사람 관찰+문구 정정·기준 적용', 'AI_AGREEMENT':'두 AI 일치', 'HUMAN_SOURCE_ONLY':'사람 원문 사실만 확인', 'UNATTRIBUTED':'출처 미상'}


def wilson(correct, total):
    if total == 0:
        return None
    z = NormalDist().inv_cdf(.975)
    p = correct / total
    denominator = 1 + z*z/total
    center = (p + z*z/(2*total)) / denominator
    half = z * math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / denominator
    return {'low':max(0.,center-half), 'high':min(1.,center+half), 'level':.95, 'method':'Wilson'}


def paired_exact(first_only, second_only):
    n = first_only + second_only
    return min(1., 2 * sum(math.comb(n,k) for k in range(min(first_only,second_only)+1)) / (2**n)) if n else 1.


def label_source(review, review_id, observation_ids, adjudicated_ids):
    if review_id in adjudicated_ids:
        return 'HUMAN_OBSERVATION_ADJUDICATED'
    if review_id in observation_ids:
        return 'HUMAN_SOURCE_ONLY'
    if review.get('method') == 'human_direct':
        return 'HUMAN_DIRECT_LABEL'
    if review.get('method') == 'ai_agreement':
        return 'AI_AGREEMENT'
    return 'UNATTRIBUTED'


def analyze(project):
    project = Path(project)
    package = project / 'docs/eval/test2/v4_predictions'
    receipt = verify_package(package)
    paths = {
        'labels': project/'eval/dataset-v2/ground_truth_test.json',
        'scores': project/'docs/eval/test2/v4_scores/human_confirmed_rescore_0bb2b985279d7afc.json',
        'human_answers': project/'eval/human_reviews/test2/human_review_result_test2_이창헌.json',
        'scope_audit': project/'eval/reconciliation-test2-v1/question_wording_scope_audit.json',
        'wording_resolution': project/'eval/human_reviews/test2/question_wording_resolution.json',
    }
    protected = {name:file_hash(path) for name,path in paths.items()}
    data = {name:json.loads(path.read_text('utf-8')) for name,path in paths.items()}
    labels, scores = data['labels'], data['scores']
    if protected['labels'] != scores['metadata']['labels_sha256']:
        raise ValueError('LABELS_DIFFER_FROM_SCORED_VERSION')
    spec = importlib.util.spec_from_file_location('audit_frozen_core', package/'implementation/backend/evaluation_core.py')
    core = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(core)
    finally:
        sys.dont_write_bytecode = previous
    predictions, traces = load_checkpoint(package/'predictions.json'), load_checkpoint(package/'traces.json')
    manifest = load_checkpoint(package/'manifest.json')
    contract_for = {str(d['document_id']):str(c['contract_id']) for c in manifest['contracts'] if c['split']=='test' for d in c['documents']}
    observed = {row['review_id'] for row in data['scope_audit']['items']}
    adjudicated = {row['review_id'] for row in data['wording_resolution']['items']}
    metrics, field_rows, errors, correctness = {}, [], [], {}
    for mode, prediction in predictions.items():
        by_source, counts, mode_errors, flags = {}, Counter(), [], {}
        for did, document in labels['documents'].items():
            cid = contract_for[did]
            for field in core.FIELDS:
                truth = document['fields'][field]
                value = prediction['documents'][did]['fields'].get(field)
                provided = value is not None and value != '' and value != 'UNKNOWN'
                correct = (provided and core.normalize(field,value)==core.normalize(field,truth['value'])) if truth['state']=='VALUE' else not provided
                scored = truth['state'] != 'ABSENT'
                key = f'{cid}/{did}/{field}'
                source = label_source(truth.get('review',{}),key,observed,adjudicated)
                group = by_source.setdefault(source,Counter())
                group['all_fields'] += 1
                group['scored'] += scored
                group['correct'] += bool(correct) and scored
                group['excluded_absent'] += not scored
                group['false_extraction_on_absent'] += not scored and not correct
                counts['scored'] += scored
                counts['correct'] += bool(correct) and scored
                counts['excluded_absent'] += not scored
                counts['false_extraction_on_absent'] += not scored and not correct
                if scored:
                    flags[key] = bool(correct)
                row = {'mode':mode,'contract_id':cid,'document_id':did,'field':field,'label_source':source,
                       'expected_state':truth['state'],'expected_value':truth['value'],'predicted_value':value,
                       'provided':provided,'correct':bool(correct),'scored':scored,'critical_field':field in CRITICAL}
                field_rows.append(row)
                if not correct:
                    review = traces[mode][did].get('review',{})
                    decision = next((d for d in review.get('decisions',[]) if d['field']==field),None)
                    row = {**row,'error_kind':'WRONG_VALUE_PRESENT' if provided else 'BLANK_OR_REVIEW',
                           'document_manual_review_required':review.get('manual_review_required'),
                           'field_marked_unresolved':field in review.get('unresolved_fields',[]),
                           'proposal_state':decision['proposal']['state'] if decision else None,
                           'proposal_applied':decision.get('applied') if decision else None,
                           'guard_reasons':decision.get('reasons',[]) if decision else []}
                    mode_errors.append(row)
                    errors.append(row)
        saved = scores['metrics'][mode]['field_counts']
        if (counts['scored'],counts['correct']) != (saved['scored'],saved['correct']):
            raise ValueError('SAVED_SCORE_MISMATCH')
        for group in by_source.values():
            group['accuracy'] = group['correct']/group['scored'] if group['scored'] else None
        metrics[mode] = {**counts,'accuracy':counts['correct']/counts['scored'],
            'wilson95':wilson(counts['correct'],counts['scored']),'by_label_source':by_source,
            'scored_error_counts':dict(Counter(e['error_kind'] for e in mode_errors if e['scored'])),
            'critical_error_counts':dict(Counter(e['error_kind'] for e in mode_errors if e['scored'] and e['critical_field']))}
        correctness[mode] = flags
    a,b = correctness['hybrid_unguarded'],correctness['hybrid_guarded']
    if a.keys()!=b.keys():
        raise ValueError('PAIRED_DENOMINATORS_DIFFER')
    paired = Counter('both_correct' if a[k] and b[k] else 'unguarded_only_correct' if a[k] else 'guarded_only_correct' if b[k] else 'both_wrong' for k in a)
    paired['mcnemar_exact_two_sided_p'] = paired_exact(paired['unguarded_only_correct'],paired['guarded_only_correct'])
    paired['guarded_minus_unguarded_percentage_points'] = 100*(sum(b.values())-sum(a.values()))/len(a)
    expected_checks = Counter(row['status'] for contract in labels['contracts'].values() for row in contract['checks'])
    report = {'format':'test2-result-audit-v1','new_inference_calls':0,'new_guard_runs':0,
        'prediction_receipt_sha256':file_hash(package/'receipt.json'),'prediction_attempt_id':receipt['attempt_id'],
        'source_hashes':protected,'account_number_evaluated':False,'evaluated_fields':list(core.FIELDS),
        'metrics':metrics,'paired_comparison':dict(paired),'expected_check_states':dict(expected_checks),
        'fail_missing_detection_measured':False,'human_source_only_check_count':len(observed),
        'adjudicated_field_ids':sorted(adjudicated),'errors':errors}
    verify_package(package)
    if protected != {name:file_hash(path) for name,path in paths.items()}:
        raise ValueError('SOURCE_CHANGED_DURING_AUDIT')
    return report, field_rows


def pct(value):
    return f'{100*value:.2f}%' if value is not None else '미측정'


def markdown(report):
    lines = ['# test2 저장 예측 추가 분석','',
        '**검출 성능 공백: test2에는 FAIL·MISSING 정답과 누락 서류 사례가 없다. 불일치·누락 검출 성능은 미측정이다.**','',
        '기존 정답·사람 답·예측 패키지는 그대로 두고 저장된 예측만 계산했다. 모델·가드·OCR·판정 재실행은 0회다.','',
        '## 정확도와 95% Wilson 구간','',
        '| 조건 | 정답/평가 칸 | 정확도 | 95% Wilson 구간 |','| --- | --- | --- | --- |']
    for mode,label in MODES.items():
        m=report['metrics'][mode];ci=m['wilson95']
        lines.append(f"| {label} | {m['correct']}/{m['scored']} | {pct(m['accuracy'])} | {pct(ci['low'])}–{pct(ci['high'])} |")
    p=report['paired_comparison']
    lines += ['',f"가드 없음만 맞은 칸 {p['unguarded_only_correct']}개, 가드 v4만 맞은 칸 {p['guarded_only_correct']}개, 둘 다 틀린 칸 {p['both_wrong']}개다. 같은 칸끼리 비교한 양측 exact McNemar p={p['mcnemar_exact_two_sided_p']:.5f}. **정답 4칸 차이(1.96%p)는 이 표본에서 통계적으로 구분할 근거가 부족하다. 동등함을 증명한 것은 아니다.**",
        'Wilson과 위 검정은 필드의 독립성 가정을 둔 참고 계산이다. 204칸은 6계약 안에 묶여 있어 상관이 있으며, 이 구간을 새로운 회사에서의 일반화 성능 보증으로 해석하지 않는다.','',
        '계산 기준: 정답 ABSENT 48칸은 기존 정확도 분모에서 제외하고 오추출은 별도로 확인했다. 계좌번호는 기존 7개 평가 필드에 없으므로 **계좌 정확도는 미측정**이다.','',
        '## 틀린 값과 빈칸·REVIEW 구분','',
        '| 조건 | 틀린 값이 남음 | 빈칸/UNKNOWN·REVIEW | 이 중 금액·사업자번호 등 핵심 칸 오류 |','| --- | --- | --- | --- |']
    for mode in ('hybrid_unguarded','hybrid_guarded'):
        m=report['metrics'][mode];c=m['scored_error_counts'];critical=m['critical_error_counts']
        lines.append(f"| {MODES[mode]} | {c.get('WRONG_VALUE_PRESENT',0)} | {c.get('BLANK_OR_REVIEW',0)} | 값 오류 {critical.get('WRONG_VALUE_PRESENT',0)} / 빈칸·REVIEW {critical.get('BLANK_OR_REVIEW',0)} |")
    lines += ['',
        '가드 v4의 9칸은 모두 빈칸/UNKNOWN으로 남은 오류이고 해당 문서는 모두 manual_review_required=true다. 가드 없는 조건의 5칸은 빈칸/UNKNOWN 4개와, 도장에 가려 읽을 수 없는 합계에 5,000,000원을 채운 1개다. 그 값에도 문서 단위 사람 확인 필요 표시는 있었다. 따라서 이를 ‘경고 없이 확신한 오류’로 단정하지 않고 **틀린 값 표시 후보**와 **확인으로 넘긴 빈칸**으로 구분한다. 실제 UI의 경고 인지는 별도 사용자 테스트가 필요하다.',
        '두 조건에서 상호 2칸은 잘못된 ABSENT 제안이 적용됐다. 문서 단위 확인 요청은 있지만 해당 필드가 unresolved_fields에는 없었다. 빈칸을 남겼다는 사실과 칸별로 정확히 안내했다는 주장은 구분한다. 가드 실패 9칸과 ‘정답 VALUE 제안 9개 거부’는 서로 다른 집계다.','',
        '| 조건 | 계약/문서/필드 | 정답 | 저장 결과 | 구분 | 핵심 |','| --- | --- | --- | --- | --- | --- |']
    for e in report['errors']:
        if e['mode'] not in {'hybrid_guarded','hybrid_unguarded'} or not e['scored']:continue
        want=str(e['expected_value']) if e['expected_state']=='VALUE' else e['expected_state']
        got='빈칸' if e['predicted_value'] is None else str(e['predicted_value'])
        lines.append(f"| {MODES[e['mode']]} | {e['contract_id']}/{e['document_id']}/{e['field']} | {want} | {got} | {'값 오류' if e['provided'] else '빈칸·확인 필요'} | {'예' if e['critical_field'] else '아니오'} |")
    source_keys=['HUMAN_DIRECT_LABEL','HUMAN_OBSERVATION_ADJUDICATED','AI_AGREEMENT']
    lines += ['', '## 정답 출처별 필드 정확도','',
        '| 조건 | 사람 직접 라벨 확인 | 사람 관찰+문구 정정·기준 적용 | 두 AI 일치 |','| --- | --- | --- | --- |']
    for mode,label in MODES.items():
        cells=[]
        for source in source_keys:
            g=report['metrics'][mode]['by_label_source'].get(source,{})
            cells.append(f"{g.get('correct',0)}/{g.get('scored',0)} · {pct(g.get('accuracy'))}")
        lines.append('| '+label+' | '+' | '.join(cells)+' |')
    lines += ['',
        '사람 결과의 81개는 분류·필드·검사 상태를 합친 원문 확인 항목 수다. 위 정확도 분모 204칸에서는 직접 라벨 확인 39칸, 사용자 관찰과 문구 정정으로 REVIEW를 유지한 1칸, 두 AI 일치 164칸으로 나뉜다. 기존 N/A 질문 18개는 원문 사실만 물었으므로 ‘사람이 N/A를 직접 확정’했다고 세지 않는다. 이 18개는 필드 정확도 분모에 포함되지 않는다.',
        '사람 표본에는 해석·모호 사례가 의도적으로 포함되어 있다. 두 출처의 난이도·필드 구성도 달라, 출처별 차이를 사람/AI 정답표의 우열로 해석하지 않는다.','',
        '## 세트 난이도와 다음 검증','',
        '규칙만의 정확도는 dev 78.34%, 기존 test 75.67%, test2 91.67%다. **77.74%는 기존 test의 가드 적용 조건**이므로 규칙만 비교에 쓰지 않는다. test2는 기존 규칙에 잘 맞는 자료 비중이 높거나 사례 구성이 쉬웠을 가능성이 있다. 다만 서로 다른 문서·서식·사례·버전이므로 수치만으로 난이도를 확정할 수 없다. FAIL·MISSING이 없는 점도 일반 검수 업무를 대표하기 어렵게 한다.',
        '중립 문구 20항목 재확인은 기존 응답과의 일치율만 별도로 보관하고 기존 정답/점수를 덮어쓰지 않는다. 같은 사람이 재확인하므로 기억·반복 효과가 남아 유도 문구의 인과 효과를 측정한 실험이라고 주장하지 않는다.',
        '동결 뒤 test3는 FAIL·MISSING을 포함하는 별도 계획으로 준비하며 지금 자료를 생성하거나 모델을 실행하지 않는다.','',
        '계산 근거: [NIST Wilson 비율 구간](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/propconf.htm), [NIST McNemar 대응 비교](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/mcnemar.htm). 원본 해시와 칸별 결과는 analysis.json, field_results.csv, errors.csv에 보존한다.']
    return '\n'.join(lines)+'\n'


def write_report(project, output):
    report, rows=analyze(project)
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'analysis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (output/'README.md').write_text(markdown(report),encoding='utf-8')
    for name,values in (('field_results.csv',rows),('errors.csv',report['errors'])):
        with (output/name).open('w',encoding='utf-8-sig',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(values[0]));writer.writeheader()
            writer.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()} for row in values)
    return report
