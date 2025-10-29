import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import time
import collections

# --- SİSTEM YAPILANDIRMASI (BASİTLEŞTİRİLMİŞ) ---
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 30
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

# --- OTOMATİK ALGILAMA PARAMETRELERİ (TEK AYAR NOKTASI) ---
# BU AYAR, SİSTEMİN HASSASİYETİNİ BELİRLER.
MIN_AUDIO_LEVEL = 0.1      # Kaydı başlatmak için gereken minimum ses seviyesi.
                             # Eğer sistem sizi duymuyorsa, bu değeri düşürün (örn: 0.003).
                             # Eğer çok fazla gürültü alıyorsa, bu değeri artırın (örn: 0.008).

SILENCE_DURATION_S = 0.7     # Kaydı bitirmek için gereken sürekli sessizlik süresi (saniye).

# --- WHISPER MODEL AYARLARI ---
MODEL_SIZE = "small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"


class AutoDetectAssistant:
    """
    Sadece ses seviyesi ve sessizlik süresine dayalı, basit ve kararlı
    otomatik algılama asistanı.
    """
    def __init__(self, model_size, device, compute_type):
        print("🔄 Whisper modeli yükleniyor...")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        print("✅ Model başarıyla yüklendi.")

        # Durum makinesi için değişkenler
        self.state = "WAITING"  # Olası durumlar: WAITING, RECORDING, PROCESSING
        self.audio_frames = []
        
        # Sessizlik sayacı için eşik değeri
        self.SILENCE_CHUNKS_THRESHOLD = int(SILENCE_DURATION_S * 1000 / CHUNK_DURATION_MS)
        self.silence_counter = 0

    def _process_audio_chunk(self, indata: np.ndarray, frames, time, status):
        """
        Her ses parçası için çağrılır ve durum makinesini çalıştırır.
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
        Kaydedilen sesi birleştirir, metne çevirir ve sistemi sıfırlar.
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
                    print(f"📝 METİN: {transcribed_text}")
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
        """Sistemi başlatır ve ana döngüyü çalıştırır."""
        print("\n" + "="*50)
        print("   OTOMATİK ALGILAMA SİSTEMİ (BASİT MOD)")
        print("="*50)
        print(f"   Hassasiyet (Minimum Ses Seviyesi): {MIN_AUDIO_LEVEL}")
        print(f"   Sessizlik Süresi: {SILENCE_DURATION_S} saniye")
        print("\n   Konuşmaya başlayın, sistem kaydı otomatik başlatacaktır.")
        print("   Sustuktan sonra transkripsiyon otomatik başlayacaktır.")
        print("\n   Programdan çıkmak için: CTRL+C")
        print("="*50)
        print("\n▶️ Sistem hazır. Sizi dinliyor...")

        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='float32',
                               blocksize=CHUNK_SAMPLES, callback=self._process_audio_chunk):
                while True:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n\n👋 Program sonlandırılıyor...")
        except Exception as e:
            print(f"\n❌ Ana programda bir hata oluştu: {e}")


def main():
    assistant = AutoDetectAssistant(
        model_size=MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE
    )
    assistant.start()

if __name__ == "__main__":
    main()