"""
services/conversation_agent_service/app/models/conversation.py

Database Models for Conversation History

Stores conversation threads and messages for analytics and context.
"""

from datetime import datetime
from typing import Optional
import enum
from sqlalchemy import String, Text, Integer, ForeignKey, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.database.base import Base, TimestampMixin


class MessageRole(str, enum.Enum):
    """Message role in conversation."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Conversation(Base, TimestampMixin):
    """
    Conversation thread.

    Represents a single conversation session between user and AI agent.
    """

    __tablename__ = "conversations"

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Session Info
    session_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
        comment="Unique session identifier"
    )

    # User Info
    user_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True,
        comment="User identifier (if authenticated)"
    )
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(20),
        index=True,
        nullable=True,
        comment="User phone number"
    )
    customer_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Customer name"
    )

    # Conversation Metadata
    language: Mapped[str] = mapped_column(
        String(10),
        default="tr",
        nullable=False,
        comment="Conversation language code (tr, en)"
    )
    channel: Mapped[str] = mapped_column(
        String(50),
        default="voice",
        nullable=False,
        comment="Communication channel (voice, web, mobile)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
        index=True,
        comment="Whether conversation is active"
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Conversation end timestamp"
    )

    # Metrics
    total_messages: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total message count"
    )
    total_tokens_used: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        comment="Total LLM tokens consumed"
    )

    # Additional Data
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional conversation metadata"
    )

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )

    # Indexes
    __table_args__ = (
        Index("idx_conversations_session_active", "session_id", "is_active"),
        Index("idx_conversations_user_created", "user_id", "created_at"),
        Index("idx_conversations_phone_created", "phone_number", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Conversation(id={self.id}, session_id={self.session_id}, "
            f"user_id={self.user_id}, messages={self.total_messages})>"
        )


class Message(Base, TimestampMixin):
    """
    Individual message in conversation.

    Stores each message exchanged between user and AI agent.
    """

    __tablename__ = "messages"

    # Primary Key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Foreign Key
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Parent conversation ID"
    )

    # Message Content
    role: Mapped[MessageRole] = mapped_column(
        SQLEnum(MessageRole),
        nullable=False,
        index=True,
        comment="Message role (user, assistant, system, tool)"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message content"
    )

    # Tool Calling
    tool_calls: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Tool calls made in this message"
    )
    tool_results: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Tool call results"
    )

    # Metrics
    tokens_used: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Tokens consumed by this message"
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Response latency in milliseconds"
    )

    # Additional Data
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional message metadata"
    )

    # Relationships
    conversation: Mapped["Conversation"] = relationship(
        "Conversation",
        back_populates="messages"
    )

    # Indexes
    __table_args__ = (
        Index("idx_messages_conversation_role", "conversation_id", "role"),
        Index("idx_messages_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return (
            f"<Message(id={self.id}, conversation_id={self.conversation_id}, "
            f"role={self.role}, content='{content_preview}')>"
        )
