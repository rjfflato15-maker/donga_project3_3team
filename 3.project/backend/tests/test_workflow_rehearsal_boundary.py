"""Windows event-loop IPC must not accidentally permit local/external API calls."""
import subprocess
import sys
from pathlib import Path


def test_event_loop_socketpair_exception_still_blocks_direct_connections():
    project = Path(__file__).resolve().parents[2]
    code = """
import socket
from backend.scripts.prepare_team_test_inbox import install_execution_boundary
counts = install_execution_boundary(allow_event_loop_socketpair=True)
left, right = socket.socketpair()
left.close()
right.close()
assert counts['network_attempts'] == 0
with socket.socket() as client:
    try:
        client.connect(('127.0.0.1', 1))
    except RuntimeError:
        pass
    else:
        raise AssertionError('Direct loopback connection was not blocked')
assert counts['network_attempts'] == 1
"""
    result = subprocess.run([sys.executable, '-c', code], cwd=project, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
