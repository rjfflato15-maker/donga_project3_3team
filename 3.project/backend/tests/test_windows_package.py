import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.launcher import environment, settings, cli, ai_setup
from backend.launcher.environment import LauncherError
from tools.installer.build_package import copy_app


def test_packaged_runtime_and_data_do_not_depend_on_developer_venv(tmp_path, monkeypatch):
    project = tmp_path / 'programs/C-Pilot'
    runtime = project / 'runtime/python/python.exe'
    runtime.parent.mkdir(parents=True)
    runtime.touch()
    monkeypatch.setattr(environment, 'PROJECT', project)
    monkeypatch.setattr(settings, 'PROJECT', project)
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'profile'))
    assert environment.python_path() == runtime
    config = settings.load_settings(tmp_path / 'missing.json')
    assert Path(config['storage_root']) == tmp_path / 'profile/C-Pilot/pilot'
    assert not Path(config['storage_root']).is_relative_to(project)
    assert config['llm_enabled'] is False
    env = environment.pilot_environment(dict(config, llm_enabled=True))
    assert env['APP_LLM_ENABLED'] == 'true' and env['APP_VLM_ENABLED'] == 'true'


def test_first_packaged_start_creates_only_a_new_empty_inbox(tmp_path, monkeypatch):
    path = tmp_path / 'launcher/settings.json'
    config = {'storage_root': str(tmp_path / 'pilot'), 'backup_directory': str(tmp_path / 'backup'),
              'port': 18057, 'intranet': False, 'llm_enabled': False, 'vlm_enabled': True}
    settings.save_settings(path, config)
    initialize = Mock()
    monkeypatch.setattr(cli, 'is_packaged', lambda: True)
    monkeypatch.setattr(cli, 'initialize', initialize)
    monkeypatch.setattr(cli, 'start', lambda *args, **kw: 'started')
    assert cli.main(['start', '--no-browser', '--settings-file', str(path)]) == 0
    initialize.assert_called_once_with(config, path.parent / 'server.json', empty=True)
    (tmp_path / 'pilot').mkdir()
    (tmp_path / 'pilot/pilot.db').touch()
    initialize.reset_mock()
    assert cli.main(['start', '--no-browser', '--settings-file', str(path)]) == 0
    initialize.assert_not_called()


def test_payload_allowlist_omits_customer_data_environment_and_team_materials(tmp_path):
    source, stage = tmp_path / 'source', tmp_path / 'payload'
    files = ['backend/app/main.py', 'backend/launcher/cli.py', 'backend/pilot_launcher.py',
        'backend/manage_pilot.py', 'C-Pilot.exe', 'frontend/dist/index.html',
        'tools/ops/scheduled_launcher.ps1', 'tools/ops/install_pilot_startup.ps1', 'tools/ops/install_pilot_backup.ps1',
        'tools/installer/customer-install.txt', *['docs/operations/' + name for name in (
            'customer_package.md', 'accounts_security.md', 'backup_restore.md', 'network.md', 'startup_settings.md', 'maintenance.md')]]
    secrets = ['.env', 'backend/.env', 'backend/env', 'backend/app/.env', 'backend/.venv/password.txt',
        'storage/pilot/pilot.db', 'storage/launcher/settings.json', 'initial-accounts.txt',
        'backend/tests/private.py', 'docs/operations/team_test_network.md', 'tmp/private.txt']
    for name in files + secrets:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('private-sentinel' if name in secrets else 'public-runtime', encoding='utf-8')
    copy_app(source, stage)
    content = [path.read_text(encoding='utf-8') for path in stage.rglob('*') if path.is_file()]
    assert content and all('private-sentinel' not in item for item in content)
    assert (stage / 'backend/app/main.py').exists() and (stage / 'frontend/dist/index.html').exists()


def test_ai_setup_preserves_config_and_does_not_stop_existing_cloud_server(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_setup.Path, 'home', lambda: tmp_path)
    config_path = tmp_path / '.ollama/server.json'
    config_path.parent.mkdir()
    config_path.write_text('{"other_option":"keep"}')
    monkeypatch.setattr(ai_setup, 'local_models', lambda _: [])
    execute = Mock()
    monkeypatch.setattr(ai_setup.subprocess, 'run', execute)
    current = {'llm_enabled': False}
    with pytest.raises(LauncherError, match='재시도'):
        ai_setup.prepare_ai(current, tmp_path / 'settings.json', session=Mock())
    assert json.loads(config_path.read_text()) == {'other_option': 'keep', 'disable_ollama_cloud': True}
    assert current['llm_enabled'] is False
    execute.assert_not_called()


def test_ai_setup_only_enables_after_installed_local_models_and_vision_are_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(ai_setup.Path, 'home', lambda: tmp_path)
    ai_setup.disable_cloud(tmp_path / '.ollama/server.json')
    models = [{'name': name, 'size': 1, 'digest': 'test-digest'} for name in ai_setup.MODELS]
    monkeypatch.setattr(ai_setup, 'local_models', lambda _: models)
    monkeypatch.setattr(ai_setup, 'installed_ollama', lambda: 'unit-ollama.exe')
    session = Mock()
    session.post.return_value.json.return_value = {'capabilities': []}
    config = {'llm_enabled': False, 'vlm_enabled': False}
    path = tmp_path / 'settings.json'
    with pytest.raises(LauncherError):
        ai_setup.prepare_ai(config, path, session=session)
    assert not path.exists() and config['llm_enabled'] is False
    session.post.return_value.json.return_value = {'capabilities': ['vision']}
    ai_setup.prepare_ai(config, path, session=session)
    assert json.loads(path.read_text())['llm_enabled'] is True
    assert session.trust_env is False


def test_unverified_ai_installer_is_never_executed(tmp_path, monkeypatch):
    verify = Mock(return_value=Mock(returncode=1))
    monkeypatch.setattr(ai_setup.subprocess, 'run', verify)
    with pytest.raises(LauncherError, match='서명'):
        ai_setup.verify_installer(tmp_path / 'OllamaSetup.exe')
