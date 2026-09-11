from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy import event

from autoflow.infrastructure.database.kernel_settings import (
    SqlAlchemyDefaultKernelRepository,
)
from autoflow.infrastructure.database.session import (
    create_session_factory,
    migrate_database,
)


def test_default_row_initialization_is_atomic_across_two_repositories(tmp_path) -> None:
    database = tmp_path / "autoflow.sqlite3"
    migrate_database(database)
    factory = create_session_factory(database)
    barrier = Barrier(2)
    engine = factory.kw["bind"]

    def synchronize_inserts(_conn, _cursor, statement, _parameters, _context, _many):
        if statement.lstrip().upper().startswith("INSERT INTO KERNEL_SETTINGS"):
            barrier.wait(timeout=2)

    event.listen(engine, "before_cursor_execute", synchronize_inserts)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            repositories = list(
                pool.map(
                    lambda _index: SqlAlchemyDefaultKernelRepository(factory), range(2)
                )
            )
    finally:
        event.remove(engine, "before_cursor_execute", synchronize_inserts)

    assert [repository.get().revision for repository in repositories] == [0, 0]
    factory.dispose()
