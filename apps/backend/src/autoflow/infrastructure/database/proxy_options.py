from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.profiles.ports import ProxyOptionRecord, ProxyPoolOptionRecord

from .models import ProxyPoolRow, ProxyRow
from .proxy_models import ProxyProjectionRow


class SqlAlchemyProxyOptions:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def list_proxies(self) -> list[ProxyOptionRecord]:
        with self.session_factory() as session:
            rows = session.execute(
                select(ProxyRow, ProxyProjectionRow)
                .outerjoin(ProxyProjectionRow, ProxyProjectionRow.proxy_id == ProxyRow.id)
                .order_by(ProxyRow.name)
            ).all()
            return [ProxyOptionRecord(row.id, row.name, _available(row, projection)) for row, projection in rows]

    def list_pools(self) -> list[ProxyPoolOptionRecord]:
        with self.session_factory() as session:
            rows = session.scalars(select(ProxyPoolRow).order_by(ProxyPoolRow.name)).all()
            return [ProxyPoolOptionRecord(row.id, row.name) for row in rows]

    def proxy_is_available(self, proxy_id: str) -> bool:
        with self.session_factory() as session:
            row = session.get(ProxyRow, proxy_id)
            return row is not None and _available(row, session.get(ProxyProjectionRow, proxy_id))

    def pool_exists(self, pool_id: str) -> bool:
        with self.session_factory() as session:
            return session.get(ProxyPoolRow, pool_id) is not None


def _available(row: ProxyRow, projection: ProxyProjectionRow | None) -> bool:
    return row.enabled and (projection is None or (
        projection.credential_available and not projection.remote_missing and not projection.stale
    ))
