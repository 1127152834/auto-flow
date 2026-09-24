"""Frozen WebRPA on_log concise semantics at AutoFlow's SSE boundary."""
from __future__ import annotations

import asyncio
import json
import socket
from contextlib import suppress

import httpx
import pytest
import uvicorn
from fastapi import FastAPI

from autoflow.adapters.events.workflows import (
    StudioEvent,
    StudioEventJournal,
    _scope_log_event,
    workflow_events_router,
)


@pytest.mark.parametrize(('log', 'keep'), [
    ({'level': 'info'}, False), ({'level': 'debug'}, False), ({'level': 'success'}, False),
    ({'level': 'warning'}, True), ({'level': 'error'}, True),
    ({'level': 'info', 'isUserLog': True}, True), ({'level': 'info', 'isSystemLog': True}, True),
])
def test_concise_delivery_matches_frozen_source_without_mutating_history(log, keep):
    original = StudioEvent(7, 'execution:log', {'runId': 'r', 'log': log})
    concise = _scope_log_event(original, False)
    assert concise == (original if keep else StudioEvent(7, 'studio:cursor', {}))
    assert _scope_log_event(original, True) is original
    assert original.data == {'runId': 'r', 'log': log}


def test_batch_filter_preserves_order_identity_and_other_event_types():
    logs = [{'level': 'info', 'id': 'a'}, {'level': 'warning', 'id': 'b'}, {'level': 'info', 'isUserLog': True, 'id': 'c'}]
    original = StudioEvent(8, 'execution:log_batch', {'runId': 'r', 'logs': logs})
    assert _scope_log_event(original, False) == StudioEvent(8, original.event, {'runId': 'r', 'logs': logs[1:]})
    assert original.data['logs'] == logs
    assert _scope_log_event(StudioEvent(9, 'execution:log_batch', {'logs': logs[:1]}), False) == StudioEvent(9, 'studio:cursor', {})
    terminal = StudioEvent(10, 'execution:completed', {'result': 'passed'})
    assert _scope_log_event(terminal, False) is terminal


@pytest.mark.asyncio
async def test_real_http_two_clients_and_reconnect_have_independent_delivery_and_full_history():
    journal = StudioEventJournal()
    await journal.publish('execution:log', {'log': {'id': 'info', 'level': 'info', 'message': '普通'}})
    await journal.publish('execution:log', {'log': {'id': 'user', 'level': 'info', 'message': '用户', 'isUserLog': True}})
    await journal.publish('execution:log_batch', {'logs': [{'id': 'debug', 'level': 'debug'}, {'id': 'error', 'level': 'error'}]})
    await journal.publish('execution:completed', {'runId': 'r'})
    app = FastAPI()
    app.include_router(workflow_events_router(journal))
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    sock.listen()
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', lifespan='off'))
    serving = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(5):
            while not server.started:
                await asyncio.sleep(.01)
        async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{sock.getsockname()[1]}', timeout=3, trust_env=False) as client:
            async def frames(query):
                received = []
                async with client.stream('GET', f'/api/events/stream?{query}') as response:
                    assert response.status_code == 200
                    frame = {}
                    async for line in response.aiter_lines():
                        if line.startswith('id: '): frame['id'] = int(line[4:])
                        elif line.startswith('event: '): frame['event'] = line[7:]
                        elif line.startswith('data: '): frame['data'] = json.loads(line[6:])
                        elif not line and frame:
                            received.append(frame)
                            if frame['id'] == 4: break
                            frame = {}
                return received
            concise, verbose = await asyncio.gather(frames('verboseLog=false'), frames('verboseLog=true'))
            assert [item['id'] for item in concise] == [1, 2, 3, 4]
            assert concise[0] == {'id': 1, 'event': 'studio:cursor', 'data': {}}
            assert concise[1] == verbose[1]
            assert [log['id'] for log in concise[2]['data']['logs']] == ['error']
            assert [log['id'] for log in verbose[2]['data']['logs']] == ['debug', 'error']
            assert await frames('afterSeq=2&verboseLog=true') == verbose[2:]
            assert await frames('afterSeq=0') == verbose
            assert (await client.get('/api/events/stream?verboseLog=invalid')).status_code == 422
        assert journal.replay(after_sequence=0)[0].data['log']['id'] == 'info'
        assert len(journal.replay(after_sequence=0)[2].data['logs']) == 2
    finally:
        server.should_exit = True
        try:
            await asyncio.wait_for(serving, 5)
        except TimeoutError:
            serving.cancel()
            with suppress(asyncio.CancelledError): await serving
        sock.close()
