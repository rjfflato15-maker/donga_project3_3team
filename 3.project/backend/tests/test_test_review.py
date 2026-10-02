"""Heldout preparation checks use hand-authored fixtures, never real test data."""
import copy
import json
import zipfile
import pytest
from backend.evaluation_core import EvaluationNotReady, validate_labels, file_hash
from backend.evaluation_review import compare_labels, merge_independent_parts, validate_reference_draft
from backend.evaluation_confirmation import apply_human_decisions
from backend.scripts.package_independent_review import package
from backend.scripts.prepare_test_review import workbook_from_comparison
from test_evaluation import source_example, independent_example

def heldout_example():
    manifest, reference = source_example()
    for row in manifest['contracts']:
        row['split'] = 'test'
    reference['split'] = 'test'
    return (manifest, reference, independent_example(manifest, reference))

def sampled_labels():
    manifest, reference, reply = heldout_example()
    comparison = compare_labels(manifest, reference, reply, sample_rate=0.1, sample_method='case_document_type')
    comparison.update(hashes={'reference': 'a' * 64, 'independent_replies': {'unit-fixture.json': 'b' * 64}}, comparison_sha256='c' * 64)
    decisions = {}
    for row in comparison['rows']:
        if not row['human_review_required']:
            continue
        expected = row['reference']
        state = expected['state'] if isinstance(expected, dict) else 'TYPE' if row['key'] == 'document_type' else 'MISSING_TYPES' if row['key'] == 'missing_types' else expected
        value = expected.get('value') if isinstance(expected, dict) else expected if state in {'TYPE', 'MISSING_TYPES'} else None
        decisions[row['review_id']] = {'state': state, 'value': value, 'confirmation': '확인', 'evidence': 'hand-authored unit fixture only'}
    return (manifest, reference, comparison, decisions)

def test_test_draft_structure_does_not_unlock_preliminary_or_confirmed_scoring():
    manifest, reference, _ = heldout_example()
    validate_reference_draft(manifest, reference, 'test')
    with pytest.raises(EvaluationNotReady):
        validate_labels(manifest, reference, 'test', allow_unreviewed=True)
    with pytest.raises(EvaluationNotReady):
        validate_labels(manifest, reference, 'test')
    assert reference['review']['confirmed'] is False

def test_test_reconciliation_preserves_real_human_and_ai_coverage():
    manifest, reference, comparison, decisions = sampled_labels()
    labels = apply_human_decisions(manifest, reference, comparison, decisions, 'unit-human')
    assert validate_labels(manifest, labels, 'test')
    assert labels['review']['human_direct_count'] == len(decisions)
    assert labels['review']['ai_agreement_count'] == len(comparison['rows']) - len(decisions)
    assert labels['review']['human_full_review'] is False
    assert all((doc['reviewed'] is False for doc in labels['documents'].values()))
    with pytest.raises(EvaluationNotReady):
        apply_human_decisions(manifest, reference, comparison, {}, 'unit-human')
    broken = copy.deepcopy(labels)
    broken['review']['human_direct_count'] += 1
    with pytest.raises(EvaluationNotReady):
        validate_labels(manifest, broken, 'test')

def test_independent_test_replies_cannot_mix_dev_or_confirmed_answers():
    _, _, reply = heldout_example()
    assert merge_independent_parts([reply], split='test')['split'] == 'test'
    with pytest.raises(EvaluationNotReady):
        merge_independent_parts([reply])
    reply['review']['confirmed'] = True
    with pytest.raises(EvaluationNotReady):
        merge_independent_parts([reply], split='test')

def test_test_blind_package_excludes_dev_design_and_reference(tmp_path):
    root = tmp_path / 'dataset'
    root.mkdir()
    rows = []
    for cid, split in ((1, 'dev'), (2, 'test')):
        file = root / f'{split}-original.txt'
        file.write_text(f'hand-authored {split}', encoding='utf-8')
        rows.append({'contract_id': cid, 'split': split, 'layout_family': split + '-fixture', 'input': {}, 'documents': [{'document_id': cid, 'path': file.name, 'sha256': file_hash(file)}]})
    (root / 'manifest.json').write_text(json.dumps({'dataset_version': 'synthetic-v1', 'created_for': 'local-evaluation', 'contracts': rows}), encoding='utf-8')
    (root / 'reference_labels_test.json').write_text('unit oracle must be excluded', encoding='utf-8')
    destination = tmp_path / 'blind-test'
    archive = package(root, destination, split='test')
    with zipfile.ZipFile(archive) as z:
        assert 'case_01/test-original.txt' in z.namelist()
        assert not any(('dev-original' in name or 'reference' in name or 'manifest.json' in name for name in z.namelist()))
        assert json.loads(z.read('case_01/reply_template.json'))['split'] == 'test'
    assert 'eval/blind-test' in (destination / 'CLAUDE_PROMPT.md').read_text(encoding='utf-8')

def test_test_workbook_starts_unconfirmed_and_keeps_row_ids(tmp_path):
    import openpyxl
    manifest, _, comparison, _ = sampled_labels()
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    comparison_path = tmp_path / 'comparison.json'
    comparison_path.write_text(json.dumps(comparison), encoding='utf-8')
    output = tmp_path / 'human-review.xlsx'
    workbook_from_comparison(tmp_path, comparison_path, output)
    book = openpyxl.load_workbook(output)
    assert book['안내']['B13'].value == 'test' and book['안내']['B12'].value is None
    ids = []
    for name in ('필드확인', '검수확인'):
        for row in book[name].iter_rows(min_row=5, values_only=True):
            ids.append(row[0])
            assert row[10] is None and row[11] is None
    book.close()
    assert set(ids) == {row['review_id'] for row in comparison['rows'] if row['human_review_required']}
    with pytest.raises(EvaluationNotReady):
        workbook_from_comparison(tmp_path, comparison_path, output)
