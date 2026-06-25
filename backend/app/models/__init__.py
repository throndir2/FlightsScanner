"""SQLModel table definitions (durable schema).

Importing this package registers all tables on ``SQLModel.metadata`` so Alembic
autogeneration and ``create_all`` can see them.
"""

from app.models.base import CabinClass, TimestampMixin
from app.models.flight_alert import FlightAlert
from app.models.flight_result import FlightResult
from app.models.user import User

__all__ = [
    "CabinClass",
    "TimestampMixin",
    "User",
    "FlightAlert",
    "FlightResult",
]
