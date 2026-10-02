"""Configuration, a bounded local health probe, and stored execution are separate."""
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from ..ai.local_llm import LLMSettings, OllamaClient, PROMPT_VERSION, CORE_FIELDS
from ..ai.grounding import canonical

_cache = {}
_lock = threading.Lock()


def llm_status(*, probe=False):
    enabled = os.getenv('APP_LLM_ENABLED','false').lower() == 'true'
    policy = os.getenv('APP_LLM_GUARD_POLICY','v3')
    cloud_file = Path.home()/'.ollama/server.json'
    try:
        cloud_disabled = json.loads(cloud_file.read_text(encoding='utf-8-sig')).get('disable_ollama_cloud') is True
    except (OSError, ValueError, TypeError):
        cloud_disabled = False
    base = {'configured_enabled':enabled, 'model':os.getenv('APP_LLM_MODEL','qwen3:latest'),
            'prompt_version':PROMPT_VERSION, 'guard_policy':policy, 'cloud_disabled':cloud_disabled,
            'connection_state':'UNCHECKED','connected':None,'checked_at':None,'error':None,
            'configuration_valid':False,'ready_for_inference':False}
    try:
        settings=LLMSettings.from_env()
        client=OllamaClient(settings)
        if policy not in {'v3','v4'}:
            raise ValueError('INVALID_GUARD_POLICY')
    except (ValueError,TypeError):
        return {**base,'connection_state':'INVALID_CONFIGURATION','error':'INVALID_LOCAL_CONFIGURATION'}
    base['configuration_valid']=True
    key=(settings.url,settings.model)
    with _lock:
        saved=_cache.get(key)
    fresh=saved and time.monotonic()-saved[0]<30
    if probe and not fresh:
        try:
            response=client.session.get(settings.url.rstrip('/')+'/api/tags',timeout=(1,2),allow_redirects=False)
            response.raise_for_status()
            entries=response.json()['models']
            local=next((m for m in entries if m.get('name')==settings.model and m.get('size')
                        and not m.get('remote_host') and not m.get('remote_model')),None)
            health={'connection_state':'CONNECTED','connected':True,'model_installed':bool(local),
                    'error':None if local else 'LOCAL_MODEL_NOT_INSTALLED'}
        except Exception:
            health={'connection_state':'UNAVAILABLE','connected':False,'model_installed':None,'error':'LOCAL_SERVER_UNAVAILABLE'}
        finally:
            client.session.close()
        health['checked_at']=datetime.now(timezone.utc).isoformat()
        with _lock:_cache[key]=(time.monotonic(),health)
        saved=(time.monotonic(),health);fresh=True
    if fresh:
        base.update(saved[1])
    else:
        base['model_installed']=None
    base['ready_for_inference']=bool(enabled and cloud_disabled and base['connected'] and base['model_installed'])
    if not probe or fresh:
        client.session.close()
    return base


def applied_value_decisions(review):
    return [d for d in (review or {}).get('decisions',[]) if isinstance(d,dict) and d.get('applied')
            and d.get('field') in CORE_FIELDS
            and (d.get('proposal') or {}).get('state') == 'VALUE'
            and canonical(d.get('field'),(d.get('proposal') or {}).get('value')) is not None]


def document_execution(stored):
    review=stored.get('ai_review') or {}
    execution=stored.get('llm_execution')
    if execution is None:
        attempts=review.get('attempts')
        execution={'configured_enabled_at_analysis':None,'status':review.get('status','UNKNOWN_LEGACY'),
                   'inference_invoked':attempts>0 if isinstance(attempts,int) else None,
                   'invocation_count':attempts,'error':review.get('error'),'recorded_at':None}
    adopted=applied_value_decisions(review)
    still_equal=[d for d in adopted if canonical(d['field'],stored.get(d['field'])) == canonical(d['field'],d['proposal']['value'])]
    return {**execution,'applied_value_field_count':len(adopted),'current_matching_ai_value_field_count':len(still_equal),
            'human_confirmed':bool(review.get('human_confirmed')),'manual_review_required':bool(review.get('manual_review_required')),
            'model':review.get('model'),'prompt_version':review.get('prompt_version'),'guard_version':review.get('guard_version')}


def contract_execution(inputs, state=None):
    docs=[document_execution(d['fields']) for d in inputs]
    known_calls=[d['invocation_count'] for d in docs if isinstance(d.get('invocation_count'),int)]
    return {'current_state':state if state is not None else llm_status(), 'document_count':len(docs),
            'invoked_document_count':sum(d['inference_invoked'] is True for d in docs),
            'unknown_execution_document_count':sum(d['inference_invoked'] is None for d in docs),
            'known_invocation_count':sum(known_calls), 'failed_document_count':sum(d['status']=='FAILED' for d in docs),
            'applied_value_field_count':sum(d['applied_value_field_count'] for d in docs),
            'current_matching_ai_value_field_count':sum(d['current_matching_ai_value_field_count'] for d in docs)}
