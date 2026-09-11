from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from autoflow.domain.profiles.ports import ProxyOptionRecord, ProxyPoolOptionRecord

from .models import ProxyPoolRow, ProxyRow


class SqlAlchemyProxyOptions:
    def __init__(self, session_factory: sessionmaker[Session]):
        self.session_factory = session_factory

    def list_proxies(self) -> list[ProxyOptionRecord]:
        with self.session_factory() as session:
            rows = session.scalars(select(ProxyRow).order_by(ProxyRow.name)).all()
            return [ProxyOptionRecord(row.id, row.name, row.enabled) for row in rows]

    def list_pools(self) -> list[ProxyPoolOptionRecord]:
        with self.session_factory() as session:
            rows = session.scalars(select(ProxyPoolRow).order_by(ProxyPoolRow.name)).all()
            return [ProxyPoolOptionRecord(row.id, row.name) for row in rows]

    def proxy_is_available(self, proxy_id: str) -> bool:
        with self.session_factory() as session:
            row = session.get(ProxyRow, proxy_id)
            return row is not None and row.enabled

    def pool_exists(self, pool_id: str) -> bool:
        with self.session_factory() as session:
            return session.get(ProxyPoolRow, pool_id) is not None
