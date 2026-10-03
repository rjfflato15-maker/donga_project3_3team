from pathlib import Path

import pytest

from backend.test2_result_analysis import analyze, label_source, paired_exact, wilson

PROJECT=Path(__file__).resolve().parents[2]


def test_wilson_boundaries_and_known_example():
    assert wilson(0,0) is None
    assert wilson(0,10)['low']==pytest.approx(0)
    assert wilson(10,10)['high']==pytest.approx(1)
    interval=wilson(5,10)
    assert interval['low']==pytest.approx(.2365930905)
    assert interval['high']==pytest.approx(.7634069095)


def test_paired_exact_uses_discordant_pairs_not_independent_denominators():
    assert paired_exact(5,1)==.21875
    assert paired_exact(1,5)==.21875
    assert paired_exact(0,0)==1
    assert paired_exact(6,0)==.03125


def test_source_fact_and_adjudication_do_not_become_direct_human_labels():
    review={'method':'human_direct'}
    assert label_source(review,'a',{'a'},set())=='HUMAN_SOURCE_ONLY'
    assert label_source(review,'a',set(),{'a'})=='HUMAN_OBSERVATION_ADJUDICATED'
    assert label_source(review,'a',set(),set())=='HUMAN_DIRECT_LABEL'


def test_saved_prediction_analysis_preserves_denominators_and_separates_deferral():
    report,rows=analyze(PROJECT)  # verifies receipt before and after; no inference imports
    m=report['metrics']
    assert [(m[k]['correct'],m[k]['scored']) for k in ('rule','llm','hybrid_unguarded','hybrid_guarded')]==[(187,204),(184,204),(199,204),(195,204)]
    assert m['hybrid_guarded']['scored_error_counts']=={'BLANK_OR_REVIEW':9}
    assert m['hybrid_unguarded']['scored_error_counts']=={'BLANK_OR_REVIEW':4,'WRONG_VALUE_PRESENT':1}
    assert m['hybrid_guarded']['critical_error_counts']=={'BLANK_OR_REVIEW':5}
    assert report['account_number_evaluated'] is False
    assert report['expected_check_states'].get('FAIL',0)==report['expected_check_states'].get('MISSING',0)==0
    assert report['paired_comparison']['mcnemar_exact_two_sided_p']==.21875
    assert len(rows)==4*252
    for mode in m.values():
        groups=mode['by_label_source']
        assert [groups[k]['scored'] for k in ('HUMAN_DIRECT_LABEL','HUMAN_OBSERVATION_ADJUDICATED','AI_AGREEMENT')]==[39,1,164]
        assert mode['false_extraction_on_absent']==0
