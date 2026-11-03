from datetime import datetime

from sqlalchemy import (
    String, Integer, DateTime, ForeignKey,
    Boolean, Float
)
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    org_type: Mapped[str] = mapped_column(
        String(40), default="hospital"
    )


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id")
    )
    name: Mapped[str] = mapped_column(String(120))
    average_minutes: Mapped[int] = mapped_column(
        Integer, default=8
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )


class Counter(Base):
    __tablename__ = "counters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id")
    )
    name: Mapped[str] = mapped_column(String(80))
    service_id: Mapped[int | None] = mapped_column(
        ForeignKey("services.id"), nullable=True
    )
    active: Mapped[bool] = mapped_column(
        Boolean, default=True
    )


class Token(Base):
    __tablename__ = "tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_number: Mapped[str] = mapped_column(
        String(20), index=True
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id")
    )
    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id")
    )
    counter_id: Mapped[int] = mapped_column(
        ForeignKey("counters.id")
    )

    customer_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(
        String(30), default=""
    )
    status: Mapped[str] = mapped_column(
        String(20), default="waiting", index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    called_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    service_minutes: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    call_count: Mapped[int] = mapped_column(
        Integer, default=0
    )

    # NEW: Estimated call time
    estimated_call_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    # NEW: SMS tracking
    confirmation_sms_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )