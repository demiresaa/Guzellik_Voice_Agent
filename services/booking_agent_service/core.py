# services/booking_agent_service/core.py

import pandas as pd
from datetime import datetime
from typing import Optional
import os

# Global DB Simülasyonu
APPOINTMENTS_DB = pd.DataFrame({
    'id': [1, 2],
    'date': ['2025-10-30', '2025-11-05'],
    'time': ['10:00', '14:30'],
    'stylist': ['Ayşe Hanım', 'Fatma Hanım'],
    'service': ['Saç Kesimi', 'Manikür'],
    'status': ['Confirmed', 'Confirmed']
})

class BookingCore:
    """Booking Agent'ın (FastMCP) Veritabanı/İş Mantığı Katmanı."""
    
    @staticmethod
    def is_available(date_str: str, time_str: str, stylist: str) -> bool:
        """Belirtilen zaman ve uzman için müsaitlik kontrolü yapar."""
        try:
            # Gerçek bir DB sorgusunu simüle eder.
            check = APPOINTMENTS_DB[
                (APPOINTMENTS_DB['date'] == date_str) & 
                (APPOINTMENTS_DB['time'] == time_str) & 
                (APPOINTMENTS_DB['stylist'] == stylist) &
                (APPOINTMENTS_DB['status'] == 'Confirmed') # Onaylanmış randevuları say
            ]
            return check.empty # Boşsa müsait demektir.
        except Exception as e:
            # Kurumsal standartlara uygun olarak, hata durumunda güvenlik için False döneriz.
            print(f"DB Kontrol Hatası: {e}")
            return False 

    @classmethod
    def book_appointment(cls, date_str: str, time_str: str, service: str, stylist: str) -> str:
        """Yeni randevu kaydı oluşturur ve .txt dosyasına kaydeder."""
        global APPOINTMENTS_DB

        # 1. Müsaitlik kontrolü
        if not cls.is_available(date_str, time_str, stylist):
            return f"HATA: {stylist} {date_str} {time_str} tarihinde maalesef doludur."

        # 2. Kayıt işlemi
        try:
            new_id = APPOINTMENTS_DB['id'].max() + 1 if not APPOINTMENTS_DB.empty else 1
            new_record = pd.DataFrame([{
                'id': new_id,
                'date': date_str,
                'time': time_str,
                'service': service,
                'stylist': stylist,
                'status': 'Confirmed'
            }])

            APPOINTMENTS_DB = pd.concat([APPOINTMENTS_DB, new_record], ignore_index=True)

            # 3. TXT dosyasına kaydet
            cls._save_appointment_to_txt(new_id, date_str, time_str, service, stylist)

            return f"BAŞARILI: Randevunuz {new_id} ID'si ile {date_str} {time_str} için başarıyla oluşturulmuştur."
        except Exception as e:
            return f"KRİTİK HATA: Randevu kaydı sırasında beklenmeyen bir sorun oluştu. Detay: {e}"

    @staticmethod
    def _save_appointment_to_txt(appointment_id: int, date_str: str, time_str: str, service: str, stylist: str):
        """Randevu bilgilerini appointments.txt dosyasına kaydeder."""
        try:
            # Proje ana dizininde 'appointments.txt' dosyası oluştur
            file_path = os.path.join(os.getcwd(), 'appointments.txt')

            # Tarih ve saat bilgisini ekle
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Dosyaya ekle (append mode)
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Randevu ID: {appointment_id}\n")
                f.write(f"Oluşturulma Zamanı: {timestamp}\n")
                f.write(f"Tarih: {date_str}\n")
                f.write(f"Saat: {time_str}\n")
                f.write(f"Hizmet: {service}\n")
                f.write(f"Uzman: {stylist}\n")
                f.write(f"Durum: Onaylandı\n")
                f.write(f"{'='*60}\n")

            print(f"✓ Randevu {appointment_id} dosyaya kaydedildi: {file_path}")
        except Exception as e:
            print(f"UYARI: Randevu txt dosyasına kaydedilemedi: {e}")