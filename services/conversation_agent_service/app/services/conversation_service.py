"""
services/conversation_agent_service/app/services/conversation_service.py

Conversation Service - Core LLM Orchestration

Orchestrates LangChain agent with tool calling, SSE streaming, and conversation history.
This is the heart of the Conversation Agent Service.
"""

import asyncio
import time
import json
from typing import Optional, AsyncGenerator, Dict, Any, List
from datetime import datetime, timedelta

import aiohttp
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import StructuredTool
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from shared.common.logging import get_logger, set_trace_context
from shared.common.exceptions import ExternalServiceException, ValidationException
from shared.common.models import SSEMessage

from app.models.conversation import MessageRole
from app.repositories.conversation_repository import ConversationRepository
from app.services.session_service import SessionService
from config import ConversationAgentSettings

logger = get_logger(__name__)


class ConversationService:
    """
    Conversation orchestration service.

    Responsibilities:
    - LangChain agent execution
    - Tool calling (Booking Agent)
    - SSE streaming
    - Conversation history management
    """

    def __init__(
        self,
        settings: ConversationAgentSettings,
        conversation_repo: ConversationRepository,
        session_service: SessionService
    ):
        """
        Initialize conversation service.

        Args:
            settings: Service configuration
            conversation_repo: Conversation repository
            session_service: Session service
        """
        self.settings = settings
        self.conversation_repo = conversation_repo
        self.session_service = session_service

        # Initialize LLM
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=settings.GEMINI_TEMPERATURE,
            max_tokens=settings.GEMINI_MAX_TOKENS,
            timeout=settings.GEMINI_TIMEOUT_SECONDS,
            convert_system_message_to_human=True,
            google_api_key=settings.GEMINI_API_KEY
        )

        # Initialize tools and agent
        self.tools = self._create_tools()
        self.agent_executor = self._create_agent()

        logger.info("ConversationService initialized", extra={
            "model": settings.GEMINI_MODEL,
            "tools_count": len(self.tools)
        })

    def _create_tools(self) -> List[StructuredTool]:
        """
        Create LangChain tools for Booking Agent integration.

        Returns:
            List of StructuredTool instances
        """
        from datetime import datetime as dt

        tools = [
            # Tool #1: Get Customer Info
            StructuredTool.from_function(
                func=self._get_customer_info,
                name="get_customer_info",
                description="""
                Müşteri telefon numarasıyla müşteri bilgilerini getir.
                Konuşma başında mutlaka kullan.
                Args:
                    phone_number (str): Telefon numarası (05XXXXXXXXX)
                Returns:
                    dict: Müşteri bilgileri, tier, geçmiş randevular
                """,
                coroutine=self._get_customer_info_async
            ),

            # Tool #2: Create/Update Customer
            StructuredTool.from_function(
                func=self._create_customer,
                name="create_customer",
                description="""
                Yeni müşteri oluştur veya güncelle.
                Args:
                    phone_number (str): Telefon
                    name (str): İsim
                    surname (str): Soyisim
                    email (str, optional): Email
                Returns:
                    dict: Oluşturma sonucu
                """,
                coroutine=self._create_customer_async
            ),

            # Tool #3: Check Availability
            StructuredTool.from_function(
                func=self._check_availability,
                name="check_availability",
                description=f"""
                Hizmetler için müsait zaman dilimlerini kontrol et.
                ÖNEMLİ: BUGÜN {dt.now().strftime('%Y-%m-%d')} - GEÇMİŞ TARİH GÖNDERİLEMEZ!
                Args:
                    services (str): Hizmet adları (virgülle ayrılmış)
                    specialist_name (str, optional): Uzman tercihi
                    date_from (str, optional): Başlangıç tarihi (YYYY-MM-DD format, BUGÜN VEYA GELECEK)
                    preferred_time (str, optional): morning/afternoon/evening
                Returns:
                    dict: Müsait slotlar
                ÖRNEK: Yarın için aramak istiyorsan date_from="{(dt.now() + timedelta(days=1)).strftime('%Y-%m-%d')}"
                """,
                coroutine=self._check_availability_async
            ),

            # Tool #4: Create Appointment
            StructuredTool.from_function(
                func=self._create_appointment,
                name="create_appointment",
                description="""
                Randevu oluştur. Önce check_availability kullan.
                Args:
                    customer_phone (str): Müşteri telefonu
                    slot_start (str): Slot başlangıç (ISO format)
                    slot_end (str): Slot bitiş (ISO format)
                    specialist_name (str): Uzman adı
                    services (str): Hizmetler (virgülle ayrılmış)
                Returns:
                    dict: Randevu bilgileri ve kod
                """,
                coroutine=self._create_appointment_async
            ),

            # Tool #5: Cancel Appointment
            StructuredTool.from_function(
                func=self._cancel_appointment,
                name="cancel_appointment",
                description="""
                Randevu iptal et.
                Args:
                    appointment_id (str, optional): Randevu kodu
                    customer_phone (str, optional): Müşteri telefonu
                    reason (str, optional): İptal nedeni
                Returns:
                    dict: İptal sonucu
                """,
                coroutine=self._cancel_appointment_async
            ),

            # Tool #6: Get Service Suggestions
            StructuredTool.from_function(
                func=self._get_suggestions,
                name="get_suggestions",
                description="""
                Tamamlayıcı hizmet önerileri al (upselling).
                Randevu oluşturduktan SONRA kullan.
                Args:
                    main_service (str): Ana hizmet
                Returns:
                    dict: Öneriler ve indirimler
                """,
                coroutine=self._get_suggestions_async
            ),

            # Tool #7: Get Active Campaigns
            StructuredTool.from_function(
                func=self._get_campaigns,
                name="get_campaigns",
                description="""
                Müşteriye özel kampanyaları getir.
                Müşteri tanındıktan sonra kontrol et.
                Args:
                    customer_id (str): Müşteri ID
                Returns:
                    dict: Aktif kampanyalar
                """,
                coroutine=self._get_campaigns_async
            ),
        ]

        return tools

    def _create_agent(self) -> Any:
        """
        Create LangChain agent runnable.

        Returns:
            Agent runnable (LangGraph-based)
        """
        # Get today's date for context
        from datetime import datetime as dt
        today = dt.now().strftime("%Y-%m-%d")

        # System instruction for Gemini
        system_instruction = f"""Sen bir Güzellik Merkezi Randevu Asistanısın.

**BUGÜNÜN TARİHİ:** {today}

**GÖREV AKIŞI:**

1. **MÜŞTERİ TANIMLAMA** (İlk adım)
   - Hemen get_customer_info kullan
   - Müşteri varsa: "Hoş geldiniz [İsim] Hanım!"
   - Müşteri yoksa: İsim/soyisim al, create_customer kullan

2. **KAMPANYA KONTROLÜ** (Müşteri tanındıktan sonra)
   - get_campaigns ile kampanyaları kontrol et
   - Varsa doğal şekilde bilgilendir

3. **RANDEVU ALMA**
   - Hizmet, tarih, uzman tercihlerini sor
   - check_availability ile slotları bul (date_from BUGÜN veya GELECEK olmalı!)
   - Seçenekleri sun
   - Onay alınca create_appointment kullan
   - Randevu kodunu söyle

4. **UPSELLING** (Randevu oluştuktan SONRA)
   - get_suggestions ile tamamlayıcı hizmetleri öner
   - Baskıcı olma, sadece bilgilendir

**KURALLAR:**
- Nazik ve profesyonel ol
- Müşterinin adını kullan
- Kampanyaları doğal bahset
- Her zaman önce müşteriyi tanımla
- Randevu kodunu mutlaka söyle
- Araçları doğru sırayla kullan
- Tarihleri hesaplarken BUGÜNÜN TARİHİNİ ({today}) kullan!

**ÖNEMLİ:** Yanıtların kısa ve net olsun. Gereksiz açıklama yapma."""

        # Configure LLM with system instruction
        llm_with_system = ChatGoogleGenerativeAI(
            model=self.settings.GEMINI_MODEL,
            temperature=self.settings.GEMINI_TEMPERATURE,
            max_tokens=self.settings.GEMINI_MAX_TOKENS,
            timeout=self.settings.GEMINI_TIMEOUT_SECONDS,
            google_api_key=self.settings.GEMINI_API_KEY,
            # System instruction for Gemini
            system_instruction=system_instruction
        )

        # Create agent (new API: llm, tools)
        return create_agent(llm_with_system, self.tools)

    # ========================================================================
    # Tool Implementations (Booking Agent Client)
    # ========================================================================

    async def _call_booking_agent(
        self,
        endpoint: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Call Booking Agent Service.

        Args:
            endpoint: API endpoint path
            data: Request payload

        Returns:
            Response JSON

        Raises:
            ExternalServiceException: If request fails
        """
        url = f"{self.settings.BOOKING_AGENT_URL}{endpoint}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=data,
                    headers={
                        "X-API-Key": self.settings.API_KEY,
                        "Content-Type": "application/json"
                    },
                    timeout=aiohttp.ClientTimeout(
                        total=self.settings.BOOKING_AGENT_TIMEOUT
                    )
                ) as response:
                    if response.status >= 400:
                        error_detail = await response.text()
                        raise ExternalServiceException(
                            "booking-agent",
                            message=f"Booking Agent error ({response.status}): {error_detail}"
                        )

                    return await response.json()

        except aiohttp.ClientError as e:
            logger.error("Booking Agent request failed", extra={
                "endpoint": endpoint,
                "error": str(e)
            })
            raise ExternalServiceException("booking-agent", original_error=e)

    async def _get_customer_info_async(self, phone_number: str) -> dict:
        """Tool #1: Get customer info"""
        return await self._call_booking_agent(
            "/api/customer/get-by-phone",
            {"phone_number": phone_number}
        )

    def _get_customer_info(self, phone_number: str) -> dict:
        """Sync wrapper"""
        return asyncio.run(self._get_customer_info_async(phone_number))

    async def _create_customer_async(
        self,
        phone_number: str,
        name: str,
        surname: str,
        email: Optional[str] = None
    ) -> dict:
        """Tool #2: Create customer"""
        return await self._call_booking_agent(
            "/api/customer/create-or-update",
            {
                "phone_number": phone_number,
                "name": name,
                "surname": surname,
                "email": email
            }
        )

    def _create_customer(
        self,
        phone_number: str,
        name: str,
        surname: str,
        email: Optional[str] = None
    ) -> dict:
        """Sync wrapper"""
        return asyncio.run(
            self._create_customer_async(phone_number, name, surname, email)
        )

    async def _check_availability_async(
        self,
        services: str,
        specialist_name: Optional[str] = None,
        date_from: Optional[str] = None,
        preferred_time: Optional[str] = None
    ) -> dict:
        """Tool #3: Check availability"""
        service_list = [s.strip() for s in services.split(",")]
        return await self._call_booking_agent(
            "/api/booking/check-availability",
            {
                "services": service_list,
                "specialist_name": specialist_name,
                "date_from": date_from,
                "preferred_time": preferred_time
            }
        )

    def _check_availability(
        self,
        services: str,
        specialist_name: Optional[str] = None,
        date_from: Optional[str] = None,
        preferred_time: Optional[str] = None
    ) -> dict:
        """Sync wrapper"""
        return asyncio.run(
            self._check_availability_async(
                services, specialist_name, date_from, preferred_time
            )
        )

    async def _create_appointment_async(
        self,
        customer_phone: str,
        slot_start: str,
        slot_end: str,
        specialist_name: str,
        services: str
    ) -> dict:
        """Tool #4: Create appointment"""
        service_list = [s.strip() for s in services.split(",")]

        selected_slot = {
            "start_time": slot_start,
            "end_time": slot_end,
            "specialist_name": specialist_name,
            "specialist_id": "spec-001",
            "duration_minutes": 60
        }

        services_payload = [
            {"service_name": svc, "specialist_name": specialist_name}
            for svc in service_list
        ]

        return await self._call_booking_agent(
            "/api/booking/create",
            {
                "customer_phone": customer_phone,
                "selected_slot": selected_slot,
                "services": services_payload
            }
        )

    def _create_appointment(
        self,
        customer_phone: str,
        slot_start: str,
        slot_end: str,
        specialist_name: str,
        services: str
    ) -> dict:
        """Sync wrapper"""
        return asyncio.run(
            self._create_appointment_async(
                customer_phone, slot_start, slot_end, specialist_name, services
            )
        )

    async def _cancel_appointment_async(
        self,
        appointment_id: Optional[str] = None,
        customer_phone: Optional[str] = None,
        reason: Optional[str] = None
    ) -> dict:
        """Tool #5: Cancel appointment"""
        return await self._call_booking_agent(
            "/api/booking/cancel",
            {
                "appointment_id": appointment_id,
                "customer_phone": customer_phone,
                "cancellation_reason": reason
            }
        )

    def _cancel_appointment(
        self,
        appointment_id: Optional[str] = None,
        customer_phone: Optional[str] = None,
        reason: Optional[str] = None
    ) -> dict:
        """Sync wrapper"""
        return asyncio.run(
            self._cancel_appointment_async(appointment_id, customer_phone, reason)
        )

    async def _get_suggestions_async(self, main_service: str) -> dict:
        """Tool #6: Get suggestions"""
        return await self._call_booking_agent(
            "/api/marketing/suggestions",
            {"main_service": main_service}
        )

    def _get_suggestions(self, main_service: str) -> dict:
        """Sync wrapper"""
        return asyncio.run(self._get_suggestions_async(main_service))

    async def _get_campaigns_async(self, customer_id: str) -> dict:
        """Tool #7: Get campaigns"""
        return await self._call_booking_agent(
            "/api/marketing/campaigns",
            {"customer_id": customer_id}
        )

    def _get_campaigns(self, customer_id: str) -> dict:
        """Sync wrapper"""
        return asyncio.run(self._get_campaigns_async(customer_id))

    # ========================================================================
    # Conversation Methods
    # ========================================================================

    async def process_message_stream(
        self,
        session_id: str,
        user_message: str,
        user_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        format_for_sse: bool = True
    ) -> AsyncGenerator[SSEMessage | str, None]:
        """
        Process user message with SSE streaming.

        Args:
            session_id: Session ID
            user_message: User's message
            user_id: User ID (optional)
            phone_number: Phone number (optional)
            metadata: Additional metadata
            format_for_sse: If True, yields SSE-formatted strings. If False, yields SSEMessage objects.

        Yields:
            SSEMessage instances or formatted strings for streaming
        """
        start_time = time.time()

        def format_yield(msg: SSEMessage):
            return msg.to_sse_format() if format_for_sse else msg

        try:
            # Set trace context for logging
            set_trace_context(trace_id=session_id, user_id=user_id)

            # Validate session
            if not await self.session_service.validate_session(session_id):
                yield format_yield(SSEMessage(
                    event="error",
                    data={"code": "INVALID_SESSION", "message": "Session not found or expired"}
                ))
                return

            # Get or create conversation
            conversation = await self.conversation_repo.find_active_by_session(session_id)

            if not conversation:
                # Create new conversation
                conversation = await self.conversation_repo.create_conversation(
                    session_id=session_id,
                    user_id=user_id,
                    phone_number=phone_number,
                    metadata=metadata
                )

            # Add user message to history
            await self.conversation_repo.add_message(
                conversation_id=conversation.id,
                role=MessageRole.USER,
                content=user_message
            )

            # Get conversation history for context
            messages = await self.conversation_repo.get_recent_messages(
                conversation.id,
                limit=self.settings.MAX_CONTEXT_MESSAGES
            )

            # Build chat history for LangChain
            chat_history = []
            for msg in messages[:-1]:  # Exclude the message we just added
                if msg.role == MessageRole.USER:
                    chat_history.append(HumanMessage(content=msg.content))
                elif msg.role == MessageRole.ASSISTANT:
                    chat_history.append(AIMessage(content=msg.content))

            # Stream agent response
            full_response = ""
            tool_calls_made = []

            yield format_yield(SSEMessage(
                event="status",
                data={"message": "İşleniyor..."}
            ))

            # Execute agent with streaming (LangGraph format)
            async for event in self.agent_executor.astream_events(
                {"messages": chat_history + [HumanMessage(content=user_message)]},
                version="v1"
            ):
                kind = event.get("event")

                # Tool call events
                if kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_calls_made.append({
                        "tool": tool_name,
                        "input": event.get("data", {}).get("input", {})
                    })

                    yield format_yield(SSEMessage(
                        event="tool_call",
                        data={"tool": tool_name, "status": "running"}
                    ))

                # LLM token streaming
                elif kind == "on_chat_model_stream":
                    content = event.get("data", {}).get("chunk", {})
                    if hasattr(content, "content") and content.content:
                        token = content.content
                        full_response += token

                        yield format_yield(SSEMessage(
                            event="token",
                            data={"token": token}
                        ))

                # Agent finished
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    # Get final messages
                    output_messages = event.get("data", {}).get("output", {}).get("messages", [])
                    if output_messages and not full_response:
                        # If we didn't stream, get the final message
                        last_msg = output_messages[-1]
                        if hasattr(last_msg, "content"):
                            full_response = last_msg.content

            # Calculate metrics
            latency_ms = int((time.time() - start_time) * 1000)

            # Save assistant response
            await self.conversation_repo.add_message(
                conversation_id=conversation.id,
                role=MessageRole.ASSISTANT,
                content=full_response,
                tool_calls={"calls": tool_calls_made} if tool_calls_made else None,
                latency_ms=latency_ms
            )

            # Refresh session TTL
            await self.session_service.refresh_session(session_id)

            # Send completion event
            yield format_yield(SSEMessage(
                event="done",
                data={
                    "session_id": session_id,
                    "latency_ms": latency_ms
                }
            ))

            logger.info("Message processed successfully", extra={
                "session_id": session_id,
                "latency_ms": latency_ms,
                "tools_used": len(tool_calls_made)
            })

        except Exception as e:
            logger.error("Error processing message", extra={
                "session_id": session_id,
                "error": str(e)
            }, exc_info=True)

            yield format_yield(SSEMessage(
                event="error",
                data={
                    "code": "PROCESSING_ERROR",
                    "message": "Bir hata oluştu, lütfen tekrar deneyin"
                }
            ))

    async def process_message_sync(
        self,
        session_id: str,
        user_message: str,
        user_id: Optional[str] = None,
        phone_number: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Process user message and return a single, complete response.

        Args:
            session_id: Session ID
            user_message: User's message
            user_id: User ID (optional)
            phone_number: Phone number (optional)
            metadata: Additional metadata

        Returns:
            The full, final response from the agent as a string.
        """
        full_response = ""
        try:
            # Call with format_for_sse=False to get raw SSEMessage objects
            async for sse_message in self.process_message_stream(
                session_id=session_id,
                user_message=user_message,
                user_id=user_id,
                phone_number=phone_number,
                metadata=metadata,
                format_for_sse=False
            ):
                if sse_message.event == "token":
                    # The data is already a dict
                    token = sse_message.data.get("token", "")
                    if token:
                        full_response += token
                elif sse_message.event == "error":
                    logger.error(f"Sync processing encountered stream error: {sse_message.data}")
                    return "Üzgünüm, bir hata oluştu."

            # After streaming, if no tokens were streamed but a final response exists
            # (e.g. from a direct tool call with no LLM response), we need to capture it.
            # The current implementation accumulates full_response during streaming,
            # which is correct for token-based responses.
            # If a non-token final response is needed, logic would be added here.

            return full_response

        except Exception as e:
            logger.error(f"Critical error in process_message_sync: {e}", exc_info=True)
            return "Sistemsel bir hata nedeniyle cevap veremiyorum."
