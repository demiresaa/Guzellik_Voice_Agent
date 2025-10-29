"""
services/conversation_agent_service/app/repositories/conversation_repository.py

Conversation Repository

Database operations for conversations and messages.
"""

from typing import Optional, List
from datetime import datetime, timedelta
from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from shared.database.repository import BaseRepository
from shared.common.exceptions import NotFoundException
from shared.common.logging import get_logger

from app.models.conversation import Conversation, Message, MessageRole

logger = get_logger(__name__)


class ConversationRepository(BaseRepository[Conversation]):
    """
    Repository for conversation operations.

    Extends BaseRepository with conversation-specific queries.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, Conversation)

    async def find_by_session_id(
        self,
        session_id: str,
        include_messages: bool = True
    ) -> Optional[Conversation]:
        """
        Find conversation by session ID.

        Args:
            session_id: Session identifier
            include_messages: Whether to load messages (default True)

        Returns:
            Conversation or None
        """
        try:
            stmt = select(Conversation).where(
                Conversation.session_id == session_id
            )

            if include_messages:
                stmt = stmt.options(selectinload(Conversation.messages))

            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("Failed to find conversation by session_id", extra={
                "session_id": session_id,
                "error": str(e)
            })
            raise

    async def find_active_by_session(self, session_id: str) -> Optional[Conversation]:
        """
        Find active conversation by session ID.

        Args:
            session_id: Session identifier

        Returns:
            Active conversation or None
        """
        try:
            stmt = select(Conversation).where(
                and_(
                    Conversation.session_id == session_id,
                    Conversation.is_active == True
                )
            ).options(selectinload(Conversation.messages))

            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()

        except Exception as e:
            logger.error("Failed to find active conversation", extra={
                "session_id": session_id,
                "error": str(e)
            })
            raise

    async def find_by_user_id(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[Conversation]:
        """
        Find conversations by user ID.

        Args:
            user_id: User identifier
            limit: Max results

        Returns:
            List of conversations
        """
        try:
            stmt = select(Conversation).where(
                Conversation.user_id == user_id
            ).order_by(
                desc(Conversation.created_at)
            ).limit(limit)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("Failed to find conversations by user_id", extra={
                "user_id": user_id,
                "error": str(e)
            })
            raise

    async def find_by_phone_number(
        self,
        phone_number: str,
        limit: int = 10
    ) -> List[Conversation]:
        """
        Find conversations by phone number.

        Args:
            phone_number: Phone number
            limit: Max results

        Returns:
            List of conversations
        """
        try:
            stmt = select(Conversation).where(
                Conversation.phone_number == phone_number
            ).order_by(
                desc(Conversation.created_at)
            ).limit(limit)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("Failed to find conversations by phone", extra={
                "phone_number": phone_number,
                "error": str(e)
            })
            raise

    async def create_conversation(
        self,
        session_id: str,
        user_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        customer_name: Optional[str] = None,
        language: str = "tr",
        channel: str = "voice",
        metadata: Optional[dict] = None
    ) -> Conversation:
        """
        Create new conversation.

        Args:
            session_id: Session identifier
            user_id: User ID (optional)
            phone_number: Phone number (optional)
            customer_name: Customer name (optional)
            language: Language code
            channel: Communication channel
            metadata: Additional metadata

        Returns:
            Created conversation
        """
        conversation = Conversation(
            session_id=session_id,
            user_id=user_id,
            phone_number=phone_number,
            customer_name=customer_name,
            language=language,
            channel=channel,
            is_active=True,
            total_messages=0,
            total_tokens_used=0,
            metadata=metadata or {}
        )

        return await self.create(conversation)

    async def add_message(
        self,
        conversation_id: int,
        role: MessageRole,
        content: str,
        tool_calls: Optional[dict] = None,
        tool_results: Optional[dict] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
        metadata: Optional[dict] = None
    ) -> Message:
        """
        Add message to conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role
            content: Message content
            tool_calls: Tool calls (optional)
            tool_results: Tool results (optional)
            tokens_used: Tokens consumed (optional)
            latency_ms: Response latency (optional)
            metadata: Additional metadata

        Returns:
            Created message
        """
        try:
            message = Message(
                conversation_id=conversation_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_results=tool_results,
                tokens_used=tokens_used,
                latency_ms=latency_ms,
                metadata=metadata or {}
            )

            self.session.add(message)
            await self.session.flush()

            # Update conversation counters
            conversation = await self.get_by_id(conversation_id)
            if conversation:
                conversation.total_messages += 1
                if tokens_used:
                    conversation.total_tokens_used += tokens_used

            await self.session.flush()
            await self.session.refresh(message)

            logger.debug("Message added to conversation", extra={
                "conversation_id": conversation_id,
                "role": role,
                "tokens": tokens_used
            })

            return message

        except Exception as e:
            logger.error("Failed to add message", extra={
                "conversation_id": conversation_id,
                "role": role,
                "error": str(e)
            })
            raise

    async def end_conversation(self, conversation_id: int) -> Conversation:
        """
        Mark conversation as ended.

        Args:
            conversation_id: Conversation ID

        Returns:
            Updated conversation
        """
        conversation = await self.get_by_id(conversation_id)

        if not conversation:
            raise NotFoundException("Conversation", str(conversation_id))

        conversation.is_active = False
        conversation.ended_at = datetime.utcnow()

        await self.session.flush()
        await self.session.refresh(conversation)

        logger.info("Conversation ended", extra={
            "conversation_id": conversation_id,
            "total_messages": conversation.total_messages
        })

        return conversation

    async def get_recent_messages(
        self,
        conversation_id: int,
        limit: int = 20
    ) -> List[Message]:
        """
        Get recent messages from conversation.

        Args:
            conversation_id: Conversation ID
            limit: Max messages to return

        Returns:
            List of recent messages
        """
        try:
            stmt = select(Message).where(
                Message.conversation_id == conversation_id
            ).order_by(
                Message.created_at
            ).limit(limit)

            result = await self.session.execute(stmt)
            return list(result.scalars().all())

        except Exception as e:
            logger.error("Failed to get recent messages", extra={
                "conversation_id": conversation_id,
                "error": str(e)
            })
            raise

    async def cleanup_old_conversations(self, days: int = 90) -> int:
        """
        Delete conversations older than specified days.

        Args:
            days: Number of days (conversations older than this will be deleted)

        Returns:
            Number of conversations deleted
        """
        try:
            from sqlalchemy import delete

            cutoff_date = datetime.utcnow() - timedelta(days=days)

            stmt = delete(Conversation).where(
                and_(
                    Conversation.is_active == False,
                    Conversation.created_at < cutoff_date
                )
            )

            result = await self.session.execute(stmt)
            await self.session.commit()

            deleted_count = result.rowcount

            logger.info("Old conversations cleaned up", extra={
                "days": days,
                "deleted_count": deleted_count
            })

            return deleted_count

        except Exception as e:
            logger.error("Failed to cleanup old conversations", extra={
                "days": days,
                "error": str(e)
            })
            raise
