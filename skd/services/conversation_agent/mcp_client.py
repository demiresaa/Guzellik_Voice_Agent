# services/conversation_agent/mcp_client.py

import requests
import json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import os
import aiohttp
import asyncio

# Ortam değişkenlerini yükle
load_dotenv()

# Statik olarak tanımlıyoruz, ancak .env'den okunması tavsiye edilir.
BOOKING_AGENT_URL = os.getenv("BOOKING_AGENT_URL")

class FastMCPClient:
    """Conversation Agent'ın kullandığı FastMCP İstemcisi."""

    async def send_task_to_booking_agent(self, task_name: str, date_str: str, time_str: str, stylist: str, service: Optional[str] = None) -> str:
        """Booking Agent'a ASYNC HTTP POST isteği gönderir ve yanıtı LLM'e uygun formatta döner."""

        payload = {
            "task_name": task_name,
            "date_str": date_str,
            "time_str": time_str,
            "stylist": stylist,
            "service": service
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(BOOKING_AGENT_URL, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    response.raise_for_status()

                    # API'den gelen FastMCPResponse'u (JSON) ayrıştır
                    data = await response.json()

                    # LLM'in kullanabileceği düz metin formatında döndür (başarılı/hata ön eki ile)
                    if data['status'] == 'SUCCESS':
                        return f"MCP_OK: {data['message']}"
                    else:
                        # Booking Agent'tan gelen iş mantığı hatası (HATA: ön ekli dize)
                        return f"MCP_ERR: {data['message']}"

        except Exception as e:
            # Ağ/Sistem hatası
            return f"KRİTİK_HATA: Booking Agent'a ulaşılamadı. Randevu işlemi yapılamıyor. Detay: {e}"

    def send_task_to_booking_agent_sync(self, task_name: str, date_str: str, time_str: str, stylist: str, service: Optional[str] = None) -> str:
        """Booking Agent'a HTTP POST isteği gönderir ve yanıtı LLM'e uygun formatta döner."""
        
        payload = {
            "task_name": task_name,
            "date_str": date_str,
            "time_str": time_str,
            "stylist": stylist,
            "service": service
        }
        
        try:
            response = requests.post(BOOKING_AGENT_URL, json=payload, timeout=5)
            response.raise_for_status() # HTTP 4xx/5xx hatalarında istisna fırlatır
            
            # API'den gelen FastMCPResponse'u (JSON) ayrıştır
            data = response.json()
            
            # LLM'in kullanabileceği düz metin formatında döndür (başarılı/hata ön eki ile)
            if data['status'] == 'SUCCESS':
                return f"MCP_OK: {data['message']}"
            else:
                # Booking Agent'tan gelen iş mantığı hatası (HATA: ön ekli dize)
                return f"MCP_ERR: {data['message']}"
            
        except requests.exceptions.RequestException as e:
            # Ağ/Sistem hatası
            return f"KRİTİK_HATA: Booking Agent'a ulaşılamadı. Randevu işlemi yapılamıyor. Detay: {e}"