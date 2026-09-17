from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from .models import Base


class AndroidDeviceRow(Base):
    __tablename__ = "android_devices"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_run_id: Mapped[str | None] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)


class AndroidResourceRow(Base):
    __tablename__ = "android_resources"

    kind: Mapped[str] = mapped_column(String(24), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
