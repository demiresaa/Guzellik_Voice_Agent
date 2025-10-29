# services/booking_agent_service/api.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from .core import BookingCore

# --- 1. FastMCP Protokol Şeması ---
class FastMCPRequest(BaseModel):
    task_name: str = Field(description="Çalıştırılacak tool: 'is_available' veya 'book_appointment'.")
    date_str: str = Field(description="Randevu tarihi (YYYY-MM-DD).")
    time_str: str = Field(description="Randevu saati (HH:MM).")
    stylist: str = Field(description="Uzman adı.")
    service: str = None # book_appointment için Optional

class FastMCPResponse(BaseModel):
    # Agent'lar arası iletişimin standart yanıt formatı
    status: str = Field(description="'SUCCESS' veya 'ERROR'")
    message: str = Field(description="İşlem sonucu (LLM'e iletilecek metin).")

app = FastAPI(title="Booking Agent - FastMCP Protocol")

@app.post("/fastmcp/booking", response_model=FastMCPResponse)
def handle_booking_task(request: FastMCPRequest):
    """Conversation Agent'tan gelen randevu görevini işler."""
    
    # Protokol kontrolü ve Tool (Core) çağrısı
    if request.task_name == "is_available":
        result = BookingCore.is_available(request.date_str, request.time_str, request.stylist)
        # LLM'in anlaması için sonuç mesajı oluşturulur.
        msg = f"MÜSAİTLİK_SONUCU: {result}"
        return FastMCPResponse(status="SUCCESS", message=msg)
    
    elif request.task_name == "book_appointment":
        if not request.service:
            raise HTTPException(status_code=400, detail="Hizmet bilgisi eksik.")
             
        result = BookingCore.book_appointment(
            request.date_str, request.time_str, request.service, request.stylist
        )
        
        # BookingCore'dan gelen BAŞARILI:/HATA: ön eklerini analiz et
        status = "SUCCESS" if result.startswith("BAŞARILI:") else "ERROR"
        return FastMCPResponse(status=status, message=result)
    
    else:
        raise HTTPException(status_code=404, detail=f"Bilinmeyen görev: {request.task_name}")