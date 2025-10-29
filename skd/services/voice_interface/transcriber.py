# services/voice_interface/transcriber.py

"""
Sesli konuşma transkripsiyon servisi
Speech-to-Text ve LLM entegrasyonu
"""

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import time

from ..conversation_agent.agent import ConversationAgent
from .config import (
    SAMPLE_RATE,
    CHANNELS,
    CHUNK_DURATION_MS,
    CHUNK_SAMPLES,
    MIN_AUDIO_LEVEL,
    SILENCE_DURATION_S,
    MODEL_SIZE,
    DEVICE,
    COMPUTE_TYPE
)


class VoiceTranscriber:
    """
    Sesli konuşmayı otomatik algılayan, metne çeviren ve LLM'e gönderen servis.

    Özellikler:
    - Otomatik konuşma algılama (ses seviyesi bazlı)
    - Real-time speech-to-text (Whisper)
    - LLM entegrasyonu (ConversationAgent)
    - Sessizlik algılama ile otomatik bitirme
    """

    def __init__(self, model_size=MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE):
        """
        VoiceTranscriber'ı başlatır.

        Args:
            model_size (str): Whisper model boyutu (tiny, base, small, medium, large)
            device (str): Kullanılacak cihaz (cpu, cuda)
            compute_type (str): Hesaplama tipi (int8, float16, float32)
        """
        print("🔄 Whisper modeli yükleniyor...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("✅ Model başarıyla yüklendi.")

        # ConversationAgent'ı başlat
        print("🔄 LLM Agent yükleniyor...")
        self.agent = ConversationAgent()
        print("✅ LLM Agent başarıyla yüklendi.")

        # Durum makinesi için değişkenler
        self.state = "WAITING"  # Olası durumlar: WAITING, RECORDING, PROCESSING
        self.audio_frames = []

        # Sessizlik sayacı için eşik değeri
        self.SILENCE_CHUNKS_THRESHOLD = int(SILENCE_DURATION_S * 1000 / CHUNK_DURATION_MS)
        self.silence_counter = 0

    def _process_audio_chunk(self, indata: np.ndarray, frames, time, status):
        """
        Her ses parçası için çağrılır ve durum makinesini çalıştırır.

        Args:
            indata (np.ndarray): Gelen ses verisi
            frames: Frame sayısı
            time: Zaman bilgisi
            status: Durum bilgisi
        """
        audio_level = np.abs(indata).mean()

        # Durum makinesi mantığı
        if self.state == "WAITING":
            # Bekleme durumunda, ses seviyesinin eşiği aşıp aşmadığını kontrol et
            if audio_level >= MIN_AUDIO_LEVEL:
                print("\n🎙️ Ses algılandı, kayıt başlıyor...")
                self.state = "RECORDING"
                self.audio_frames.append(indata.copy())

        elif self.state == "RECORDING":
            # Kayıt durumunda, konuşmanın devam edip etmediğini kontrol et
            print(f"\r🔴 Kaydediliyor... (Ses Seviyesi: {audio_level:.4f})", end="")

            if audio_level >= MIN_AUDIO_LEVEL:
                # Konuşma devam ediyor, sessizlik sayacını sıfırla
                self.silence_counter = 0
                self.audio_frames.append(indata.copy())
            else:
                # Sessizlik algılandı, sayacı artır
                self.silence_counter += 1

                # Yeterli süre sessizlik olduysa, transkripsiyonu tetikle
                if self.silence_counter >= self.SILENCE_CHUNKS_THRESHOLD:
                    self.state = "PROCESSING"
                    print("\n⏹️ Yeterli sessizlik algılandı, transkripsiyon başlıyor...")
                    self._trigger_transcription()

    def _trigger_transcription(self):
        """
        Kaydedilen sesi birleştirir, metne çevirir, LLM'e gönderir ve sistemi sıfırlar.
        """
        if not self.audio_frames:
            print("⚠️ Hiç ses kaydedilmedi.")
        else:
            try:
                audio_data = np.concatenate(self.audio_frames).flatten().astype(np.float32)

                segments, _ = self.model.transcribe(audio_data, language="tr", beam_size=5)
                transcribed_text = " ".join([seg.text for seg in segments]).strip()

                print("\n" + "="*50)
                if transcribed_text:
                    print(f"📝 SİZ: {transcribed_text}")

                    # Transkribe edilen metni LLM'e gönder
                    print("🤖 Asistan düşünüyor...")
                    llm_response = self.agent.converse(transcribed_text)
                    print(f"🤖 ASİSTAN: {llm_response}")
                else:
                    print("⚠️ Metin anlaşılamadı veya kayıt çok kısaydı.")
                print("="*50)

            except Exception as e:
                print(f"❌ Transkripsiyon sırasında bir hata oluştu: {e}")

        # Her durumda sistemi sıfırla ve tekrar bekleme moduna al
        self.audio_frames.clear()
        self.silence_counter = 0
        self.state = "WAITING"
        print("\n▶️ Sistem hazır. Sizi dinliyor...")

    def start(self):
        """
        Sesli asistan sistemini başlatır ve ana döngüyü çalıştırır.
        """
        print("\n" + "="*50)
        print("   SESLİ RANDEVU ASİSTANI SİSTEMİ")
        print("="*50)
        print(f"   Hassasiyet (Minimum Ses Seviyesi): {MIN_AUDIO_LEVEL}")
        print(f"   Sessizlik Süresi: {SILENCE_DURATION_S} saniye")
        print("\n   🎙️ Konuşmaya başlayın, sistem kaydı otomatik başlatacaktır.")
        print("   🤖 Sustuktan sonra mesajınız LLM asistana gönderilecektir.")
        print("\n   Programdan çıkmak için: CTRL+C")
        print("="*50)
        print("\n▶️ Sistem hazır. Sizi dinliyor...")

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype='float32',
                blocksize=CHUNK_SAMPLES,
                callback=self._process_audio_chunk
            ):
                while True:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n👋 Program sonlandırılıyor...")
        except Exception as e:
            print(f"\n❌ Ana programda bir hata oluştu: {e}")
