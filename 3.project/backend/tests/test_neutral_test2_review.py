from pathlib import Path

import pytest

from backend.neutral_test2_review import FORMAT,prepare,compare,normalize,write_new_or_identical

PROJECT=Path(__file__).resolve().parents[2]


def test_neutral_sample_is_reproducible_without_answer_leakage():
    public,manifest,private=prepare(PROJECT)
    assert prepare(PROJECT)==(public,manifest,private)
    assert manifest['population_count']==81
    assert len(public['items'])==len(set(manifest['selected_ids']))==20
    assert manifest['selected_ids'][0]=='401/40102/supply_amount'
    assert manifest['selected_ids'][-1]=='403/contract/REQUIRED_DOCUMENTS/inspection_confirmation'
    for q in public['items']:
        assert not {'excel','q','baseline','correct','expected_value'} & q.keys()
        assert '맞아요' not in q['prompt']+q['hint']
    for case in public['cases'].values():
        assert 'fields' not in case and 'doctype' not in case
        assert all('type' not in d for d in case['docs'])
        for d in case['docs']:
            assert all((PROJECT/'eval/human_review_page_test2_neutral'/v).is_file() for v in d['views'])
    facts=[q for q in private['items'] if q['construct']=='SOURCE_FACT_ONLY']
    assert len(facts)==5
    assert all(q['choice']!='N/A' for q in facts)


@pytest.fixture
def synthetic_answers():
    """In-memory fixture only. Never saved as a real person's review."""
    public,_,private=prepare(PROJECT)
    return {'format':FORMAT,'selection_id':public['selection_id'],'reviewer':'TEST_ONLY',
        'responses':[{'id':q['id'],'choice':q['choice'],'value':q['value'],'reviewed_at':'2026-10-03T00:00:00Z'} for q in private['items']]}


def test_comparison_counts_uncertainty_and_unanswered_separately(synthetic_answers):
    synthetic_answers['responses'][0]['choice']='UNSURE'
    synthetic_answers['responses'][1]['choice']='UNREADABLE'
    synthetic_answers['responses'].pop(2)
    result=compare(PROJECT,synthetic_answers)
    assert result['counts']=={'AGREE':17,'DISAGREE':1,'UNCERTAIN':1,'UNANSWERED':1}
    assert result['agreement_among_comparable']==pytest.approx(17/18)
    assert result['agreement_over_all_selected']==.85
    assert result['by_construct']['SOURCE_FACT_ONLY']['DISAGREE']==1
    assert result['labels_or_original_answers_changed'] is False
    assert result['complete'] is False


@pytest.mark.parametrize('bad',['duplicate','unknown','version','blank_value','invalid_choice','missing_time','reviewer'])
def test_rejects_misaligned_or_incomplete_value_records(synthetic_answers,bad):
    if bad=='duplicate':synthetic_answers['responses'].append(synthetic_answers['responses'][0])
    elif bad=='unknown':synthetic_answers['responses'][0]['id']='not-in-sample'
    elif bad=='version':synthetic_answers['selection_id']='wrong'
    elif bad=='blank_value':synthetic_answers['responses'][0]['value']=''
    elif bad=='invalid_choice':synthetic_answers['responses'][0]['choice']='made-up'
    elif bad=='missing_time':synthetic_answers['responses'][0].pop('reviewed_at')
    elif bad=='reviewer':synthetic_answers['reviewer']=''
    with pytest.raises(ValueError):compare(PROJECT,synthetic_answers)


def test_amount_normalization_and_overwrite_protection(tmp_path):
    assert normalize('4,110,000원','amount')=='4110000'
    assert normalize('0','amount')=='0'
    with pytest.raises(ValueError):normalize('4.1만','amount')
    path=tmp_path/'answer.json'
    write_new_or_identical(path,'first')
    with pytest.raises(ValueError):write_new_or_identical(path,'second')
    assert path.read_text()=='first'
