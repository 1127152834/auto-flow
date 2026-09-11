from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ProxyPoolRow, ProxyRow


class SqlAlchemyProxyOptions:
    def __init__(self, session: Session):
        self.session = session

    def list_proxies(self):
        return list(self.session.scalars(select(ProxyRow).order_by(ProxyRow.name)))

    def list_pools(self):
        return list(self.session.scalars(select(ProxyPoolRow).order_by(ProxyPoolRow.name)))
