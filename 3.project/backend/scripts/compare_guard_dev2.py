"""DEV2 only: collect fixed inputs/responses, then compare guard policies.

No heldout documents, labels or predictions are opened. Scores are preliminary.
"""
import argparse
import json
import os
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT))
from backend.evaluation_core import EvaluationNotReady, file_hash, verify_dataset, verify_freeze, score_predictions
from backend.evaluation_review import validate_reference_draft
from backend.prediction_artifacts import write_json, save_checkpoint, load_checkpoint
from backend.scripts.compare_llm_modes import collect_inputs, request_cached, validate_mode_contracts, check_accuracy, guard_outcomes
from backend.app.ai.local_llm import OllamaClient, LLMSettings, PROMPT_VERSION
from backend.app.ai.llm_supplement import apply_proposals


def implementation_hash(path):
    return sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()


def development_data(root):
    if root.resolve() != (PROJECT / 'eval/dataset-v2').resolve():
        raise EvaluationNotReady('ONLY_DEV2_IS_ALLOWED')
    manifest_path = root / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    contracts = [c for c in manifest['contracts'] if c['split'] == 'dev']
    if not contracts or any(c['contract_id'] // 100 != 3 for c in contracts):
        raise EvaluationNotReady('INVALID_DEV2_CONTRACTS')
    labels_path = root / 'reference_labels_dev.json'
    labels = json.loads(labels_path.read_text(encoding='utf-8'))
    validate_reference_draft(manifest, labels, 'dev')
    verify_freeze(manifest_path, labels_path)
    verify_dataset(root, manifest, split='dev')
    return contracts, labels, manifest_path, labels_path


def collect(root, output):
    contracts, _, manifest_path, labels_path = development_data(root)
    inputs_path = output / 'inputs.json'
    if inputs_path.exists():
        inputs = load_checkpoint(inputs_path)
    else:
        inputs = collect_inputs(root, contracts)
        save_checkpoint(inputs_path, inputs)
    client = OllamaClient(LLMSettings(model='qwen3:latest'))
    config = Path.home() / '.ollama/server.json'
    if not config.exists() or json.loads(config.read_text(encoding='utf-8-sig')).get('disable_ollama_cloud') is not True:
        raise EvaluationNotReady('OLLAMA_CLOUD_MUST_BE_DISABLED')
    receipt_path = output / 'input_receipt.json'
    receipt = {'dataset_manifest_sha256':file_hash(manifest_path), 'labels_sha256':file_hash(labels_path),
               'inputs_sha256':file_hash(inputs_path), 'model':client.model_metadata(),
               'settings':asdict(client.settings), 'prompt_version':PROMPT_VERSION,
               'human_confirmed':False, 'split':'dev2', 'test_sources_opened':False}
    if receipt_path.exists():
        if json.loads(receipt_path.read_text(encoding='utf-8')) != receipt:
            raise EvaluationNotReady('DEV2_INPUTS_OR_MODEL_CHANGED')
    else:
        write_json(receipt_path, receipt, exclusive=True)
    responses = {}
    for index, (did, item) in enumerate(sorted(inputs.items()), 1):
        if item['targets']:
            run, key, hit, _ = request_cached(client, item, item['targets'], output / 'responses')
        else:
            run, key, hit = {'ok':True,'proposals':{},'elapsed_seconds':0}, None, False
        responses[did] = {'run':run, 'response_id':key}
        print(f'dev2 응답 보존 {index}/{len(inputs)} · 캐시={hit}', flush=True)
    path = output / 'fixed_responses.json'
    if path.exists():
        if load_checkpoint(path) != responses:
            raise EvaluationNotReady('DEV2_RESPONSE_CHANGED')
    else:
        save_checkpoint(path, responses)


def compare(root, output):
    contracts, labels, manifest_path, labels_path = development_data(root)
    inputs = load_checkpoint(output / 'inputs.json')
    fixed = load_checkpoint(output / 'fixed_responses.json')
    receipt = json.loads((output / 'input_receipt.json').read_text(encoding='utf-8'))
    if (receipt['inputs_sha256'] != file_hash(output / 'inputs.json') or receipt['dataset_manifest_sha256'] != file_hash(manifest_path)
            or receipt['labels_sha256'] != file_hash(labels_path)):
        raise EvaluationNotReady('DEV2_SOURCE_CHANGED')
    metrics, traces = {}, {}
    for mode in ('rule', 'hybrid_unguarded', 'hybrid_guard_v3', 'hybrid_guard_v4'):
        fields, traces[mode] = {}, {}
        for did, item in inputs.items():
            response = fixed[did]
            if mode == 'rule':
                fields[did] = item['fields']
                review = {}
            else:
                fields[did], review = apply_proposals(item['fields'], response['run'], item['pages'], item['document_type'],
                    item['targets'], guarded=mode != 'hybrid_unguarded', guard_policy='v4' if mode.endswith('v4') else 'v3')
            traces[mode][did] = {'review':review, 'response_id':response['response_id']}
        prediction = validate_mode_contracts(contracts, inputs, fields)
        metric = score_predictions(contracts, labels, prediction)
        metric['check_state_counts'] = check_accuracy(labels, prediction)
        metric['check_state_accuracy'] = metric['check_state_counts']['accuracy']
        metric['unexpected_pass_on_not_applicable'] = sum(
            f['kind']=='check' and f['expected']=='N/A' and f['actual']=='PASS' for f in metric['failures'])
        if mode.startswith('hybrid_guard_'):
            metric['guard_outcomes'] = guard_outcomes(traces[mode], labels)
        metrics[mode] = metric
    metadata = {'phase':'preliminary_dev2_unconfirmed', 'human_confirmed':False, 'test_sources_opened':False,
                'model':'qwen3:latest', 'prompt_version':PROMPT_VERSION, 'same_inputs_targets_responses':True,
                'new_inference_calls':0, 'labels_sha256':file_hash(labels_path),
                'fixed_responses_sha256':file_hash(output / 'fixed_responses.json'),
                'v4_sha256':implementation_hash(PROJECT / 'backend/app/ai/grounding_v4.py'),
                'code_hash_policy':'SHA256 with CRLF normalized to LF',
                'implementation_sha256':{name:implementation_hash(PROJECT / name) for name in (
                    'backend/app/ai/grounding.py','backend/app/ai/grounding_v4.py',
                    'backend/app/ai/local_llm.py','backend/app/ai/llm_supplement.py',
                    'backend/evaluation_core.py','backend/scripts/compare_guard_dev2.py')},
                'evaluated_at':datetime.now(timezone.utc).isoformat()}
    write_json(output / 'preliminary_comparison.json', {'metadata':metadata, 'metrics':metrics})
    write_json(output / 'preliminary_traces.json', traces)
    print(json.dumps({'phase':metadata['phase'], 'metrics':{mode:{k:metric[k] for k in ('field_accuracy','check_state_accuracy','wrong_pass_counts')}
                      for mode,metric in metrics.items()}}, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect', action='store_true')
    parser.add_argument('--dataset', type=Path, default=PROJECT / 'eval/dataset-v2')
    parser.add_argument('--output', type=Path, default=PROJECT / 'docs/eval/dev2/guard_v4')
    args = parser.parse_args(argv)
    previous = dict(os.environ)
    try:
        with tempfile.TemporaryDirectory(prefix='guard-dev2-') as storage:
            os.environ.update(APP_DEPLOYMENT_MODE='pilot', APP_NTS_MODE='disabled', APP_STORAGE_ROOT=storage)
            collect(args.dataset, args.output) if args.collect else compare(args.dataset, args.output)
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print('dev2 가드 비교 중단: '+str(exc)[:120], file=sys.stderr)
        return 2
    finally:
        os.environ.clear(); os.environ.update(previous)


if __name__ == '__main__':
    raise SystemExit(main())
