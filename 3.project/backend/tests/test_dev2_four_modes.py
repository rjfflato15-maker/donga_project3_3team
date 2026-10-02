import json,shutil
import pytest
from backend.prediction_artifacts import save_checkpoint,write_json,file_hash,ArtifactError
from backend.scripts.compare_modes_dev2 import rescore,verify,PROJECT


def package(tmp_path):
    root=tmp_path/'package';root.mkdir();(root/'implementation').mkdir()
    manifest={'dataset_version':'synthetic-hard-v2','contracts':[{'contract_id':301,'split':'dev','documents':[{'document_id':30101}],
                'check_slots':[{'rule_id':'X','field':'x'}]}]}
    values={'company_name':'A','business_registration_no':'2208812345','supply_amount':100,'tax_amount':10,'total_amount':110,'issue_date':'2026-10-01','amount_scope':'FULL'}
    labels={'dataset_version':'synthetic-hard-v2','split':'dev','review':{'reviewer_type':'source_reference','confirmed':False,'author':'unit author','created_at':'2026-10-03'},
            'contracts':{'301':{'source_checked':True,'missing_types':[],'checks':[{'rule_id':'X','field':'x','status':'PASS'}]}},
            'documents':{'30101':{'source_checked':True,'document_type':'contract','fields':{key:{'state':'VALUE','value':value} for key,value in values.items()}}}}
    prediction={'documents':{'30101':{'document_type':'contract','fields':values}},'contracts':{'301':{'checks':[{'rule_id':'X','field':'x','status':'PASS'}]}}}
    modes=('rule','llm','hybrid_unguarded','hybrid_guarded_v4')
    save_checkpoint(root/'manifest.json',manifest);write_json(root/'source_manifest.json',manifest)
    save_checkpoint(root/'predictions.json',{mode:prediction for mode in modes})
    save_checkpoint(root/'traces.json',{mode:{'30101':{'effective_seconds':.1}} for mode in modes})
    for name in ('evaluation_core.py','prediction_scoring.py'):shutil.copyfile(PROJECT/'backend'/name,root/'implementation'/name)
    receipt={'format':'dev2-four-modes-v1','attempt_id':'unit','files_sha256':{p.relative_to(root).as_posix():file_hash(p) for p in root.rglob('*') if p.is_file()}}
    write_json(root/'receipt.json',receipt)
    path=tmp_path/'labels.json';write_json(path,labels)
    write_json(path.with_suffix('.freeze.json'),{'manifest_sha256':file_hash(root/'source_manifest.json'),'labels_sha256':file_hash(path)})
    return root,path,labels


def test_dev2_relabels_change_score_without_ocr_model_guard_or_rule_calls(tmp_path,monkeypatch):
    root,path,labels=package(tmp_path)
    def forbidden(*a,**kw):raise AssertionError('rescore must not infer or validate again')
    monkeypatch.setattr('backend.app.ai.local_llm.OllamaClient.extract',forbidden)
    monkeypatch.setattr('backend.app.ai.llm_supplement.apply_proposals',forbidden)
    monkeypatch.setattr('backend.app.validation.engine.RuleEngine.validate_contract_evidence',forbidden)
    a=rescore(root,path,preliminary=True)
    labels['documents']['30101']['fields']['total_amount']['value']=121
    write_json(path,labels)
    write_json(path.with_suffix('.freeze.json'),{'manifest_sha256':file_hash(root/'source_manifest.json'),'labels_sha256':file_hash(path)})
    b=rescore(root,path,preliminary=True)
    assert a['metrics']['llm']['field_accuracy']>b['metrics']['llm']['field_accuracy']
    assert b['metadata']['new_inference_calls']==0 and b['metadata']['new_guard_runs']==0
    with pytest.raises(ValueError,match='확정한'):rescore(root,path)


def test_dev2_frozen_prediction_tampering_fails(tmp_path):
    root,path,_=package(tmp_path)
    (root/'predictions.json').write_text('{}')
    with pytest.raises(ArtifactError,match='CHANGED'):verify(root)
