"""Review-integrity tests use private fixtures, not heldout answers or originals."""
import json
import zipfile
from hashlib import sha256
import pytest
from backend.evaluation_core import EvaluationNotReady, file_hash
from backend.prediction_artifacts import write_json
from backend.scripts import prepare_test2_review as prep


def frozen_project(tmp_path,monkeypatch):
    p=prep.paths(tmp_path)
    guard=tmp_path/'guard.py';guard.write_text('original guard',encoding='utf-8')
    dev=tmp_path/'docs/eval/dev2/guard_v4'
    write_json(dev/'preliminary_comparison.json',{'metadata':{'v4_sha256':file_hash(guard)}})
    write_json(dev/'input_receipt.json',{'model':{'name':'qwen3:latest','digest':'fixed-model'},
        'prompt_version':'grounded-fields-v3','settings':{'temperature':0}})
    write_json(p['dataset']/'manifest.json',{'dataset_version':'synthetic-hard-v2'})
    monkeypatch.setattr(prep,'policy_hashes',lambda _: {'backend/app/ai/grounding_v4.py':file_hash(guard)})
    return p,guard


def blind_fixture(tmp_path):
    p=prep.paths(tmp_path)
    p['blind'].mkdir(parents=True)
    (p['blind']/'replies').mkdir()
    (p['blind']/'document.pdf').write_bytes(b'fixture-original')
    (p['blind']/'CLAUDE_PROMPT.md').write_text('eval/claude_blind_review 폴더 내부',encoding='utf-8')
    record={'dataset_version':'synthetic-hard-v2','split':'test',
        'contains_reference_answers':False,'contains_app_predictions':False,
        'files':{name:file_hash(p['blind']/name) for name in ('document.pdf','CLAUDE_PROMPT.md')}}
    write_json(p['blind']/'package_receipt.json',record)
    with zipfile.ZipFile(p['blind'].with_suffix('.zip'),'w') as archive:
        for name in (*record['files'],'package_receipt.json'):
            archive.write(p['blind']/name,name)
    return p


def test_release_is_idempotent_and_does_not_require_gold(tmp_path,monkeypatch):
    p,_=frozen_project(tmp_path,monkeypatch)
    prep.freeze_policy(tmp_path)
    digest=file_hash(p['output']/'release_lock.json')
    prep.freeze_policy(tmp_path)
    assert file_hash(p['output']/'release_lock.json')==digest
    assert not (p['dataset']/'reference_labels_test.json').exists()
    assert not (p['dataset']/'final_evaluation_attempt.json').exists()


@pytest.mark.parametrize('change',['guard','manifest'])
def test_release_refuses_changed_guard_or_dataset(tmp_path,monkeypatch,change):
    p,guard=frozen_project(tmp_path,monkeypatch)
    prep.freeze_policy(tmp_path)
    if change=='guard':
        guard.write_text('changed guard',encoding='utf-8')
    else:
        write_json(p['dataset']/'manifest.json',{'dataset_version':'changed'})
    with pytest.raises(EvaluationNotReady):
        prep.freeze_policy(tmp_path)


def test_missing_blind_replies_cannot_create_review_or_confirm_gold(tmp_path,monkeypatch):
    p=prep.paths(tmp_path)
    (p['blind']/'replies').mkdir(parents=True)
    monkeypatch.setattr(prep,'freeze_policy',lambda _: {})
    monkeypatch.setattr(prep,'verify_blind',lambda _: {})
    with pytest.raises(EvaluationNotReady,match='실제 판독 JSON 6개'):
        prep.reconcile(tmp_path,p['blind']/'replies')
    assert not p['workbook'].exists() and not p['comparison'].exists()


def test_zip_tampering_is_rejected_even_if_local_files_are_unchanged(tmp_path):
    p=blind_fixture(tmp_path)
    prep.verify_blind(p)
    with zipfile.ZipFile(p['blind'].with_suffix('.zip'),'w') as archive:
        archive.writestr('unrelated.json','{}')
    with pytest.raises(EvaluationNotReady,match='ZIP 파일 목록'):
        prep.verify_blind(p)


def test_prompt_path_update_preserves_original_and_remains_idempotent(tmp_path,monkeypatch):
    p=blind_fixture(tmp_path)
    original=(p['blind']/'document.pdf').read_bytes()
    monkeypatch.setattr(prep,'freeze_policy',lambda _: {})
    prep.update_blind_prompt(tmp_path)
    prompt=(p['blind']/'CLAUDE_PROMPT.md').read_text(encoding='utf-8')
    assert 'eval/claude_blind_review_test2 폴더' in prompt
    assert 'test2 case_01~06' in prompt
    assert (p['blind']/'document.pdf').read_bytes()==original
    digest=file_hash(p['blind'].with_suffix('.zip'))
    prep.update_blind_prompt(tmp_path)
    assert file_hash(p['blind'].with_suffix('.zip'))==digest


def test_old_human_result_hash_is_not_accepted_for_test2(tmp_path,monkeypatch):
    p=prep.paths(tmp_path)
    p['workbook'].parent.mkdir(parents=True)
    p['workbook'].write_bytes(b'new-test2-workbook')
    result=tmp_path/'old-result.json'
    write_json(result,{'split':'test','reviewer':'reviewer',
        'source_xlsx_sha256':sha256(b'old-test-workbook').hexdigest(),'items':[]})
    monkeypatch.setattr(prep,'freeze_policy',lambda _: {})
    with pytest.raises(EvaluationNotReady,match='기존 test 결과를 재사용하지 않습니다'):
        prep.confirm(tmp_path,result)
    assert not p['human'].exists()
