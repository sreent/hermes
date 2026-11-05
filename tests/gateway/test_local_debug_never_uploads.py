"""``/debug`` never uploads: it saves the report on the machine running Hermes (FORK.md).

A local session's ``/debug local`` returns the redacted report for the client to show. Every other
``/debug``, from any platform, saves the report + full logs as an archive under the profile's
``logs/debug-reports/`` and replies with its path. Neither form opens a network connection.
"""
import socket
import zipfile
from unittest.mock import patch

import pytest

from gateway.config import Platform
from gateway.platforms.base import MessageEvent
from gateway.session import SessionSource


def _runner():
    from gateway.run import GatewayRunner
    runner = object.__new__(GatewayRunner)
    runner._running_agents = {}

    async def _inline(fn, *args):
        return fn(*args)

    runner._run_in_executor_with_context = _inline
    return runner


def _event(platform, text):
    source = SessionSource(platform=platform, chat_id='chat-1', user_id='u1', chat_type='dm')
    return MessageEvent(text=text, source=source)


class _NoNetwork:
    """Any socket connect fails the test."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        raise AssertionError('network call during /debug')


@pytest.mark.asyncio
@pytest.mark.parametrize('text', ['/debug local', '/debug LOCAL', '/debug nous local'])
async def test_local_session_debug_local_returns_the_report(text):
    guard = _NoNetwork()
    bundle = {'report': 'REDACTED-REPORT-BODY', 'agent.log': 'FULL-LOG'}
    with patch('hermes_cli.debug.collect_share_bundle', return_value=bundle), \
            patch.object(socket.socket, 'connect', guard):
        out = await _runner()._handle_debug_command(_event(Platform.LOCAL, text))
    assert guard.calls == []
    assert 'REDACTED-REPORT-BODY' in out
    assert 'http' not in out.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(('platform', 'text'), [
    (Platform.TELEGRAM, '/debug'), (Platform.TELEGRAM, '/debug local'), (Platform.LOCAL, '/debug')])
async def test_debug_saves_the_archive_on_the_host_and_replies_with_its_path(tmp_path, monkeypatch, platform, text):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    guard = _NoNetwork()
    bundle = {'report': 'REPORT-BODY', 'agent.log': 'FULL-LOG'}
    with patch('hermes_cli.debug.collect_share_bundle', return_value=bundle), \
            patch.object(socket.socket, 'connect', guard), \
            patch('socket.create_connection', guard):
        out = await _runner()._handle_debug_command(_event(platform, text))
    assert guard.calls == []
    archive, = (tmp_path / 'logs' / 'debug-reports').glob('hermes-debug-*.zip')
    assert str(archive) in out
    with zipfile.ZipFile(archive) as saved:
        assert saved.read('report.txt') == b'REPORT-BODY'
        assert saved.read('agent.log') == b'FULL-LOG'


@pytest.mark.asyncio
async def test_unsavable_report_replies_with_the_error(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    with patch('hermes_cli.debug.collect_share_bundle', return_value={'report': 'x'}), \
            patch('hermes_cli.debug_archive.save_debug_archive', side_effect=PermissionError('read-only volume')):
        out = await _runner()._handle_debug_command(_event(Platform.TELEGRAM, '/debug'))
    assert 'read-only volume' in out


@pytest.mark.asyncio
async def test_local_debug_local_real_collector_opens_no_socket(tmp_path, monkeypatch):
    """The real collector, unpatched: no socket connect is reached."""
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    guard = _NoNetwork()
    with patch.object(socket.socket, 'connect', guard), \
            patch.object(socket.socket, 'connect_ex', guard), \
            patch('socket.create_connection', guard):
        out = await _runner()._handle_debug_command(_event(Platform.LOCAL, '/debug local'))
    assert guard.calls == []
    assert 'hermes dump' in out
