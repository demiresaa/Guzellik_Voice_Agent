#!/usr/bin/env python3
# main.py

"""
Güzellik Salonu Sesli Randevu Asistanı
Ana Entry Point

Kullanım:
    python main.py
"""

from skd.services.voice_interface import VoiceTranscriber


def main():
    """
    Sesli asistan sistemini başlatır.
    """
    try:
        # VoiceTranscriber'ı başlat
        transcriber = VoiceTranscriber()

        # Sistemi çalıştır
        transcriber.start()

    except KeyboardInterrupt:
        print("\n\n👋 Güle güle!")
    except Exception as e:
        print(f"\n❌ Sistem başlatılırken hata oluştu: {e}")
        print("\nLütfen şunları kontrol edin:")
        print("  - .env dosyasında GEMINI_API_KEY tanımlı mı?")
        print("  - Gerekli paketler yüklü mü? (pip install -r requirements.txt)")


if __name__ == "__main__":
    main()
