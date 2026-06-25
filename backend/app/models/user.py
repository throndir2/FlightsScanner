"""``User`` table — the system of record for application identity.

Reconciled with the NextAuth session by email; see ``docs/auth-and-security.md``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship

from app.models.base import TimestampMixin

if TYPE_CHECKING:  # avoid circular imports at runtime
    from app.models.flight_alert import FlightAlert


class User(TimestampMixin, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    email: str = Field(max_length=320, index=True, unique=True, nullable=False)
    # Null for OAuth-only accounts (no local password).
    hashed_password: str | None = Field(default=None, max_length=255)
    display_name: str | None = Field(default=None, max_length=120)
    is_active: bool = Field(default=True, nullable=False)

    alerts: list["FlightAlert"] = Relationship(
        back_populates="user",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "passive_deletes": True},
    )
