from datetime import datetime
import enum
from typing import List

from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, Enum, func, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship, declarative_mixin

from app.core.database import Base

@declarative_mixin
class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now())
    # SQLAlchemy automatically adds `updated_at = CURRENT_TIMESTAMP` to every UPDATE statement it generates
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    

# ------ Messages -------

class MessageStatus(enum.Enum):
    FETCHED = "fetched"
    CLASSIFIED = "classified"
    PLANNED = "planned"
    ACTIONED = "actioned"
    FAILED = "failed"

class MessageCategory(enum.Enum):
    APPLY = "apply"
    INTERVIEW = "interview"
    REPLY_NEEDED = "reply_needed"
    IGNORE = "ignore"


# Tell SQLAlchemy to store enum.value (e.g. "fetched") instead of enum.name ("FETCHED").
_enum_values = lambda x: [e.value for e in x]


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(), nullable=False)
    from_address: Mapped[str] = mapped_column(String(), nullable=False)
    subject: Mapped[str] = mapped_column(String(), nullable=False)
    received_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    body_text: Mapped[str | None] = mapped_column(String())
    body_html: Mapped[str | None] = mapped_column(String())
    body_markdown: Mapped[str] = mapped_column(String(), default="")
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus, values_callable=_enum_values))

    # email classification
    category: Mapped[MessageCategory | None] = mapped_column(Enum(MessageCategory, values_callable=_enum_values))
    confidence_score: Mapped[float | None] = mapped_column(Float())
    model_reasoning: Mapped[str | None] = mapped_column(String())

    attachments: Mapped[List["Attachment"]] = relationship(back_populates="message")


# ------ Attachements -------

class Attachment(Base):
    __tablename__ = "attachments"

    attachment_id: Mapped[str] = mapped_column(String(), primary_key=True)
    filename: Mapped[str] = mapped_column(String(), nullable=False)
    mime_type: Mapped[str] = mapped_column(String())
    size_bytes: Mapped[int] = mapped_column(Integer())
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))

    message: Mapped["Message"] = relationship(back_populates="attachments")


# ------ Actions --------

class ActionType(enum.Enum):
    SEND_REPLY = "send_reply"
    CALENDAR_EVENT = "calendar_event"
    JOB_APPLY = "job_apply"


class ActionStatus(enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    APPROVED = "approved"
    AWAITING_APPROVAL = "awaiting_approval"
    REJECTED = "rejected"
    FAILED = "failed"

class Action(Base, TimestampMixin):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer(), primary_key=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    action_type: Mapped[ActionType] = mapped_column(Enum(ActionType, values_callable=_enum_values))
    status: Mapped[ActionStatus] = mapped_column(Enum(ActionStatus, values_callable=_enum_values))
    payload: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON(), nullable=True)
    error: Mapped[str | None] = mapped_column(String(), nullable=True)
    