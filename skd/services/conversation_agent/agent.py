# services/conversation_agent/agent.py

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from dotenv import load_dotenv
import os
import re
import json

from .mcp_client import FastMCPClient

# Ortam değişkenlerini yükle
load_dotenv()

class ConversationAgent:
    def __init__(self):
        if not os.getenv("GEMINI_API_KEY"):
            raise EnvironmentError("GEMINI_API_KEY .env dosyasında tanımlı olmalıdır.")

        # Gemini API key'i GOOGLE_API_KEY olarak da set et (LangChain için)
        os.environ["GOOGLE_API_KEY"] = os.getenv("GEMINI_API_KEY")

        self.mcp_client = FastMCPClient()

        # convert_system_message_to_human=True, Gemini'nin sistem mesajlarını daha iyi anlamasını sağlar.
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            temperature=0.7,
            convert_system_message_to_human=True
        )

        # Konuşma geçmişi
        self.conversation_history = []

        # Sistem prompt'u
        self.system_prompt = """Sen bir Güzellik Merkezi Randevu Asistanısın.

Görevin:
1. Müşteri ile nazik ve profesyonel konuş
2. Randevu oluşturmak veya müsaitlik kontrol etmek için gerekli bilgileri topla:
   - Tarih (YYYY-MM-DD formatında)
   - Saat (HH:MM formatında)
   - Uzman ismi (örn: Ayşe Hanım, Fatma Hanım)
   - Hizmet türü (örn: Saç Kesimi, Manikür, Pedikür)

3. Tüm bilgileri aldıktan sonra, işlemi gerçekleştirmek için şu formatta komut ver:
   [RANDEVU_KONTROL: tarih=YYYY-MM-DD, saat=HH:MM, uzman=İsim] - Müsaitlik kontrolü için
   [RANDEVU_OLUSTUR: tarih=YYYY-MM-DD, saat=HH:MM, uzman=İsim, hizmet=Hizmet] - Randevu oluşturmak için

Örnek konuşma:
Müşteri: "Yarın saat 10'da Ayşe Hanım'dan randevu almak istiyorum"
Sen: "Tabii, hangi hizmet için randevu oluşturmak istersiniz?"
Müşteri: "Saç kesimi"
Sen: [RANDEVU_OLUSTUR: tarih=2025-10-28, saat=10:00, uzman=Ayşe Hanım, hizmet=Saç kesimi]

Eksik bilgi varsa önce sor, sonra komutu ver."""

    async def converse_async(self, user_input: str) -> str:
        """Kullanıcı girdisini ASENKRON olarak alır ve yanıt üretir."""
        try:
            # Kullanıcı mesajını geçmişe ekle
            self.conversation_history.append(HumanMessage(content=user_input))

            # LLM'e mesajları gönder
            messages = [SystemMessage(content=self.system_prompt)] + self.conversation_history
            response = await self.llm.ainvoke(messages)

            response_text = response.content

            # Komutları kontrol et
            if "[RANDEVU_KONTROL:" in response_text or "[RANDEVU_OLUSTUR:" in response_text:
                response_text = await self._handle_booking_commands(response_text)

            # AI yanıtını geçmişe ekle
            self.conversation_history.append(AIMessage(content=response_text))

            return response_text

        except Exception as e:
            print(f"HATA: {e}")
            return f"Üzgünüm, bir sorunla karşılaştım: {e}"

    async def _handle_booking_commands(self, response_text: str) -> str:
        """Randevu komutlarını işler."""

        # RANDEVU_KONTROL komutunu ara
        kontrol_pattern = r'\[RANDEVU_KONTROL:\s*tarih=([^,]+),\s*saat=([^,]+),\s*uzman=([^\]]+)\]'
        kontrol_match = re.search(kontrol_pattern, response_text)

        if kontrol_match:
            tarih = kontrol_match.group(1).strip()
            saat = kontrol_match.group(2).strip()
            uzman = kontrol_match.group(3).strip()

            # MCP Client'a istek gönder
            result = await self.mcp_client.send_task_to_booking_agent(
                task_name="is_available",
                date_str=tarih,
                time_str=saat,
                stylist=uzman
            )

            # Komutu sonuçla değiştir
            response_text = re.sub(kontrol_pattern, result.replace("MCP_OK:", "").replace("MCP_ERR:", ""), response_text)

        # RANDEVU_OLUSTUR komutunu ara
        olustur_pattern = r'\[RANDEVU_OLUSTUR:\s*tarih=([^,]+),\s*saat=([^,]+),\s*uzman=([^,]+),\s*hizmet=([^\]]+)\]'
        olustur_match = re.search(olustur_pattern, response_text)

        if olustur_match:
            tarih = olustur_match.group(1).strip()
            saat = olustur_match.group(2).strip()
            uzman = olustur_match.group(3).strip()
            hizmet = olustur_match.group(4).strip()

            # MCP Client'a istek gönder
            result = await self.mcp_client.send_task_to_booking_agent(
                task_name="book_appointment",
                date_str=tarih,
                time_str=saat,
                stylist=uzman,
                service=hizmet
            )

            # Komutu sonuçla değiştir
            response_text = re.sub(olustur_pattern, result.replace("MCP_OK:", "").replace("MCP_ERR:", ""), response_text)

        return response_text

    def converse(self, user_input: str) -> str:
        """Kullanıcı girdisini SENKRON olarak alır (CLI için)."""
        import asyncio
        # CLI için senkron wrapper - async metodu çağırır
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(self.converse_async(user_input))
