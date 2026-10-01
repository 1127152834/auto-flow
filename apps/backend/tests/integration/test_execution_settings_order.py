"""Remediation M1 R1-07: persisted revision, dispatcher and worker never disagree."""

import asyncio
import threading

import pytest

from autoflow.application.settings.execution import ExecutionSettingsService
from autoflow.domain.settings.execution_capacity import GIB, HardwareProfile
from autoflow.infrastructure.database.app_settings import (
    AppSettingConflict,
    SqlAlchemyAppSettings,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)

HARDWARE = HardwareProfile(8, 16 * GIB)  # recommends 6


class FakeDispatcher:
    capacity, live_capacity, paused = 0, 0, None
    fail_next = False

    def set_capacity(self, capacity, live):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("apply failed")
        self.capacity, self.live_capacity = capacity, live

    def pause_dispatch(self, reason):
        self.paused = reason


class FakeWorker:
    capacity = 0

    def set_capacity(self, capacity):
        self.capacity = capacity


class GatedStore:
    """Holds one put() after it is durable, before the service applies it."""

    def __init__(self, inner):
        self.inner, self.gate_next = inner, False
        self.durable, self.release = threading.Event(), threading.Event()
        self.fail_next = False
        self.fail_after_commit = False

    def get(self, key):
        return self.inner.get(key)

    def put(self, key, value, expected_revision):
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("disk full")
        revision = self.inner.put(key, value, expected_revision)
        if self.fail_after_commit:
            self.fail_after_commit = False
            raise RuntimeError("connection lost after commit")
        if self.gate_next:
            self.gate_next = False
            self.durable.set()
            assert self.release.wait(10)
        return revision


@pytest.fixture
def parts(tmp_path):
    database = tmp_path / "settings.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    repository = SqlAlchemyAppSettings(factory)
    store = GatedStore(repository)
    dispatcher, worker = FakeDispatcher(), FakeWorker()
    service = ExecutionSettingsService(store, lambda: HARDWARE, lambda: False)
    service.bind(dispatcher, worker)
    yield service, store, repository, dispatcher, worker
    factory.dispose()


def assert_consistent(repository, dispatcher, worker, view):
    value, revision = repository.get("execution.maxRunningBrowsers")
    assert revision == view.revision
    configured = (value or {}).get("maxRunningBrowsers")
    effective = 6 if configured is None else configured
    assert (dispatcher.capacity, dispatcher.live_capacity, worker.capacity) == (effective, 2 * effective, 2 * effective)
    assert view.capacity.effective == effective


async def wait_durable(store):
    await asyncio.get_running_loop().run_in_executor(None, store.durable.wait, 10)


@pytest.mark.asyncio
async def test_initialize_applies_the_recommendation_then_the_persisted_value(parts):
    service, _, repository, dispatcher, worker = parts
    await service.initialize()
    assert (dispatcher.capacity, dispatcher.live_capacity, worker.capacity) == (6, 12, 12)
    repository.put("execution.maxRunningBrowsers", {"maxRunningBrowsers": 3}, 0)

    restarted = ExecutionSettingsService(repository, lambda: HARDWARE, lambda: False)
    fresh_dispatcher, fresh_worker = FakeDispatcher(), FakeWorker()
    restarted.bind(fresh_dispatcher, fresh_worker)
    await restarted.initialize()
    assert (fresh_dispatcher.capacity, fresh_dispatcher.live_capacity, fresh_worker.capacity) == (3, 6, 6)
    assert (await restarted.read()).revision == 1


@pytest.mark.asyncio
async def test_a_reader_and_a_second_writer_cannot_pass_a_write_that_is_not_applied_yet(parts):
    service, store, repository, dispatcher, worker = parts
    store.gate_next = True
    first = asyncio.create_task(service.update(3, 0))
    await wait_durable(store)
    assert repository.get("execution.maxRunningBrowsers")[1] == 1  # durable, not applied
    reader = asyncio.create_task(service.read())
    second = asyncio.create_task(service.update(4, 1))
    await asyncio.sleep(0.2)
    assert not reader.done() and not second.done()
    assert dispatcher.capacity == 6  # still the recommendation applied before the write; revision 1 not applied
    store.release.set()
    first_view, read_view, second_view = await asyncio.gather(first, reader, second)
    assert (first_view.revision, read_view.revision, second_view.revision) == (1, 1, 2)
    assert read_view.capacity.effective == 3
    assert_consistent(repository, dispatcher, worker, await service.read())
    assert dispatcher.capacity == 4


@pytest.mark.asyncio
async def test_two_first_writes_leave_exactly_one_winner(parts):
    service, _, repository, dispatcher, worker = parts
    results = await asyncio.gather(service.update(2, 0), service.update(5, 0), return_exceptions=True)
    wins = [r for r in results if not isinstance(r, BaseException)]
    losses = [r for r in results if isinstance(r, AppSettingConflict)]
    assert len(wins) == 1 and len(losses) == 1 and losses[0].current_revision == 1
    assert_consistent(repository, dispatcher, worker, await service.read())


def test_concurrent_first_inserts_in_threads_map_to_one_conflict(parts):
    _, _, repository, _, _ = parts
    barrier = threading.Barrier(2)
    outcomes = []

    def write(value):
        barrier.wait()
        try:
            outcomes.append(repository.put("execution.maxRunningBrowsers", {"maxRunningBrowsers": value}, 0))
        except AppSettingConflict as conflict:
            outcomes.append(conflict)

    threads = [threading.Thread(target=write, args=(value,)) for value in (2, 3)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(type(item).__name__ for item in outcomes) == ["AppSettingConflict", "int"]
    assert repository.get("execution.maxRunningBrowsers")[1] == 1


@pytest.mark.asyncio
async def test_a_failed_persist_applies_nothing(parts):
    service, store, repository, dispatcher, worker = parts
    await service.initialize()
    store.fail_next = True
    with pytest.raises(RuntimeError, match="disk full"):
        await service.update(2, 0)
    view = await service.read()
    assert view.revision == 0 and view.capacity.configured is None
    assert_consistent(repository, dispatcher, worker, view)


@pytest.mark.asyncio
async def test_an_error_after_the_commit_is_reconciled_from_the_database_on_the_next_call(parts):
    service, store, repository, dispatcher, worker = parts
    await service.initialize()
    store.fail_after_commit = True
    with pytest.raises(RuntimeError, match="connection lost"):
        await service.update(2, 0)
    # The second write used the stale revision 0 and would 409 forever without a re-read.
    view = await service.update(3, 1)
    assert view.revision == 2 and view.capacity.configured == 3
    assert_consistent(repository, dispatcher, worker, view)


@pytest.mark.asyncio
async def test_cancelling_the_request_after_the_write_is_durable_still_applies_it(parts):
    service, store, repository, dispatcher, worker = parts
    store.gate_next = True
    request = asyncio.create_task(service.update(3, 0))
    await wait_durable(store)
    request.cancel()
    with pytest.raises(asyncio.CancelledError):
        await request
    store.release.set()
    await service.shutdown()  # waits for the owned operation
    assert_consistent(repository, dispatcher, worker, await service.read())
    assert dispatcher.capacity == 3


@pytest.mark.asyncio
async def test_cancelling_a_request_that_is_still_waiting_settles_consistently(parts):
    service, store, repository, dispatcher, worker = parts
    store.gate_next = True
    holder = asyncio.create_task(service.update(3, 0))
    await wait_durable(store)
    waiting = asyncio.create_task(service.update(4, 1))
    await asyncio.sleep(0.1)
    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting
    store.release.set()
    await holder
    await service.shutdown()
    assert_consistent(repository, dispatcher, worker, await service.read())


@pytest.mark.asyncio
async def test_a_failed_apply_pauses_dispatch_and_the_next_read_verifies_the_stored_value(parts):
    service, _, repository, dispatcher, worker = parts
    await service.initialize()
    dispatcher.fail_next = True
    with pytest.raises(RuntimeError, match="apply failed"):
        await service.update(3, 0)
    assert dispatcher.paused  # no dispatch against an unknown limit
    assert repository.get("execution.maxRunningBrowsers")[1] == 1  # the value itself is durable
    view = await service.read()  # re-reads the authoritative value and re-applies it
    assert dispatcher.paused is None
    assert view.revision == 1
    assert_consistent(repository, dispatcher, worker, view)
