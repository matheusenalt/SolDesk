"""Hashes de refresh mobile; nenhum token bruto é persistido."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models import now


class MobileRefreshToken(Base):
    __tablename__ = "mobile_refresh_token"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organization.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    session_hash: Mapped[str] = mapped_column(ForeignKey("auth_session.token_hash"), unique=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revogado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
