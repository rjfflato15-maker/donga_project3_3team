"""DEV2 four-condition comparison and pure rescoring, separate from heldout test2."""
import argparse
import importlib.util
import json
import os
import shutil
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
from uuid import uuid4

PROJECT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT))
from backend.prediction_artifacts import load_checkpoint,save_checkpoint,write_json,file_hash,digest,ArtifactError


def frozen_module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def verify(output):
    receipt=json.loads((output/'receipt.json').read_text(encoding='utf-8'))
    required={'manifest.json','source_manifest.json','predictions.json','traces.json','implementation/evaluation_core.py','implementation/prediction_scoring.py'}
    if receipt.get('format')!='dev2-four-modes-v1' or not required<=set(receipt.get('files_sha256',{})):
        raise ArtifactError('INVALID_DEV2_PACKAGE')
    for name,expected in receipt['files_sha256'].items():
        path=(output/name).resolve()
        if not path.is_relative_to(output.resolve()) or file_hash(path)!=expected:raise ArtifactError('DEV2_PACKAGE_CHANGED')
    return receipt


def rescore(output,labels_path,*,preliminary=False):
    receipt=verify(output)
    core=frozen_module(output/'implementation/evaluation_core.py','dev2_frozen_core')
    scorer=frozen_module(output/'implementation/prediction_scoring.py','dev2_frozen_scoring')
    manifest=load_checkpoint(output/'manifest.json')
    labels=json.loads(labels_path.read_text(encoding='utf-8'))
    freeze=json.loads(labels_path.with_suffix('.freeze.json').read_text(encoding='utf-8'))
    if freeze.get('manifest_sha256')!=file_hash(output/'source_manifest.json') or freeze.get('labels_sha256')!=file_hash(labels_path):
        raise ArtifactError('DEV2_LABEL_FREEZE_CHANGED')
    contracts=core.validate_labels(manifest,labels,'dev',allow_unreviewed=preliminary)
    predictions=load_checkpoint(output/'predictions.json');traces=load_checkpoint(output/'traces.json')
    metrics={}
    for mode,prediction in predictions.items():
        result=core.score_predictions(contracts,labels,prediction)
        checks=scorer.check_accuracy(labels,prediction)
        result.update(check_state_accuracy=checks['accuracy'],check_state_counts=checks,
                      mean_document_seconds=sum(t['effective_seconds'] for t in traces[mode].values())/len(traces[mode]),
                      llm_failure_count=sum(t.get('review',{}).get('status')=='FAILED' for t in traces[mode].values()),
                      unexpected_pass_on_not_applicable=sum(f['kind']=='check' and f['expected']=='N/A' and f['actual']=='PASS'
                          for f in result['failures']))
        if mode=='hybrid_guarded_v4':result['guard_outcomes']=scorer.guard_outcomes(core,traces[mode],labels)
        metrics[mode]=result
    return {'metadata':{'phase':'preliminary_dev2_unconfirmed' if preliminary else 'human_confirmed_dev2_rescore',
                        'human_confirmed':not preliminary,'prediction_attempt_id':receipt['attempt_id'],
                        'prediction_receipt_sha256':file_hash(output/'receipt.json'),'labels_sha256':file_hash(labels_path),
                        'new_inference_calls':0,'new_guard_runs':0,'test2_sources_opened':False,
                        'reporting_code_sha256':file_hash(Path(__file__)),
                        'timing_definition':'Recorded OCR/rules plus model elapsed; guard time was not measured in dev2. Not end-to-end latency or human work time.'},'metrics':metrics}


def collect(output):
    from backend.scripts.compare_guard_dev2 import development_data
    from backend.scripts.compare_llm_modes import validate_mode_contracts
    from backend.evaluation_predictions import request_once
    from backend.app.ai.local_llm import CORE_FIELDS,LLMSettings,OllamaClient,PROMPT_VERSION
    from backend.app.ai.llm_supplement import apply_proposals
    from backend.app.ai.grounding_v4 import GUARD_VERSION
    dataset=PROJECT/'eval/dataset-v2';existing=PROJECT/'docs/eval/dev2/guard_v4'
    contracts,_,manifest_path,labels_path=development_data(dataset)
    if (output/'receipt.json').exists():return verify(output)
    inputs=load_checkpoint(existing/'inputs.json');fixed=load_checkpoint(existing/'fixed_responses.json')
    original=json.loads((existing/'input_receipt.json').read_text(encoding='utf-8'))
    if original['inputs_sha256']!=file_hash(existing/'inputs.json'):raise ArtifactError('DEV2_INPUTS_CHANGED')
    client=OllamaClient(LLMSettings(**original['settings']))
    if client.model_metadata()!=original['model'] or PROMPT_VERSION!=original['prompt_version']:
        raise ArtifactError('DEV2_MODEL_OR_PROMPT_CHANGED')
    cloud=Path.home()/'.ollama/server.json'
    if not cloud.is_file() or json.loads(cloud.read_text(encoding='utf-8-sig')).get('disable_ollama_cloud') is not True:
        raise ArtifactError('CLOUD_DISABLE_CONFIG_REQUIRED')
    definition={'manifest_sha256':file_hash(manifest_path),'inputs_sha256':file_hash(existing/'inputs.json'),
                'hybrid_responses_sha256':file_hash(existing/'fixed_responses.json'),'settings':asdict(client.settings),
                'model':original['model'],'prompt_version':PROMPT_VERSION,'guard_version':GUARD_VERSION,
                'guard_sha256':file_hash(PROJECT/'backend/app/ai/grounding_v4.py'),
                'nts_mode':'disabled','split':'dev','test2_sources_opened':False}
    header=output/'execution.json'
    if header.exists():
        execution=load_checkpoint(header)
        if execution['definition']!=definition:raise ArtifactError('DEV2_EXECUTION_POLICY_CHANGED')
    else:
        execution={'attempt_id':str(uuid4()),'definition':definition,'started_at':datetime.now(timezone.utc).isoformat()}
        save_checkpoint(header,execution)
        save_checkpoint(output/'manifest.json',json.loads(manifest_path.read_text(encoding='utf-8')))
        shutil.copyfile(manifest_path,output/'source_manifest.json')
        save_checkpoint(output/'hybrid_responses.json',fixed)
        save_checkpoint(output/'inputs.json',inputs)
    field_sets={m:{} for m in ('rule','llm','hybrid_unguarded','hybrid_guarded_v4')}
    traces={m:{} for m in field_sets}
    for index,(did,item) in enumerate(sorted(inputs.items()),1):
        raw,key,hit=request_once(client,item,CORE_FIELDS,output,execution['attempt_id'])
        field_sets['rule'][did]=item['fields']
        traces['rule'][did]={'effective_seconds':item['rule_seconds']}
        fields,review=apply_proposals(item['fields'],raw,item['pages'],item['document_type'],CORE_FIELDS,guarded=False,llm_only=True,guard_policy='v4')
        field_sets['llm'][did]=fields
        traces['llm'][did]={'review':review,'response_id':key,'effective_seconds':item['rule_seconds']+raw.get('elapsed_seconds',0)}
        for mode in ('hybrid_unguarded','hybrid_guarded_v4'):
            run=fixed[did]['run']
            fields,review=apply_proposals(item['fields'],run,item['pages'],item['document_type'],item['targets'],
                                          guarded=mode=='hybrid_guarded_v4',guard_policy='v4')
            field_sets[mode][did]=fields
            traces[mode][did]={'review':review,'response_id':fixed[did]['response_id'],
                               'effective_seconds':item['rule_seconds']+run.get('elapsed_seconds',0)}
        print(f'dev2 네 조건 {index}/{len(inputs)} · LLM-only 캐시={hit}',flush=True)
    if definition['guard_sha256']!=file_hash(PROJECT/'backend/app/ai/grounding_v4.py'):
        raise ArtifactError('DEV2_GUARD_CHANGED_DURING_RUN')
    predictions={mode:validate_mode_contracts(contracts,inputs,fields) for mode,fields in field_sets.items()}
    for name,value in (('predictions.json',predictions),('traces.json',traces)):
        target=output/name
        if target.exists():
            if load_checkpoint(target)!=value:raise ArtifactError('DEV2_PREDICTIONS_CHANGED')
        else:save_checkpoint(target,value)
    implementation=output/'implementation';implementation.mkdir(exist_ok=True)
    for name in ('evaluation_core.py','prediction_scoring.py'):
        shutil.copyfile(PROJECT/'backend'/name,implementation/name)
    for folder in ('ai','validation','schemas'):
        for source in (PROJECT/'backend/app'/folder).glob('*.py'):
            target=implementation/'app'/folder/source.name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
    receipt={'format':'dev2-four-modes-v1','attempt_id':execution['attempt_id'],'frozen_at':datetime.now(timezone.utc).isoformat(),
             'definition':definition,'document_count':len(inputs),
             'files_sha256':{p.relative_to(output).as_posix():file_hash(p) for p in sorted(output.rglob('*')) if p.is_file() and p.name!='receipt.json'}}
    write_json(output/'receipt.json',receipt,exclusive=True)
    return verify(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect',action='store_true')
    parser.add_argument('--labels',type=Path,default=PROJECT/'eval/dataset-v2/reference_labels_dev.json')
    parser.add_argument('--preliminary',action='store_true')
    parser.add_argument('--output',type=Path,default=PROJECT/'docs/eval/dev2/four_modes')
    args=parser.parse_args()
    if args.collect:
        previous=dict(os.environ)
        try:
            with tempfile.TemporaryDirectory(prefix='dev2-four-modes-') as storage:
                os.environ.update(APP_DEPLOYMENT_MODE='pilot',APP_NTS_MODE='disabled',APP_STORAGE_ROOT=storage,APP_LLM_ENABLED='false')
                collect(args.output)
        finally:
            os.environ.clear();os.environ.update(previous)
    report=rescore(args.output,args.labels,preliminary=args.preliminary)
    score_dir=args.output.parent/'four_mode_scores'
    phase=report['metadata']['phase']
    destination=score_dir/(phase+'_'+file_hash(args.labels)[:16]+'_'+digest(report)[:12]+'.json')
    if not destination.exists():write_json(destination,report,exclusive=True)
    elif json.loads(destination.read_text(encoding='utf-8'))!=report:raise ArtifactError('EXISTING_SCORE_CHANGED')
    print(json.dumps({'phase':phase,'score_file':str(destination),'metrics':{m:{k:v[k] for k in ('field_accuracy','check_state_accuracy','wrong_pass_counts')} for m,v in report['metrics'].items()}},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
