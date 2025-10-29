# services/voice_interface/config.py

"""
Voice Interface konfigürasyon ayarları
"""

# --- SİSTEM YAPILANDIRMASI ---
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_DURATION_MS = 30
CHUNK_SAMPLES = int(SAMPLE_RATE * CHUNK_DURATION_MS / 1000)

# --- OTOMATİK ALGILAMA PARAMETRELERİ ---
# BU AYAR, SİSTEMİN HASSASİYETİNİ BELİRLER.
MIN_AUDIO_LEVEL = 0.1      # Kaydı başlatmak için gereken minimum ses seviyesi.
                             # Eğer sistem sizi duymuyorsa, bu değeri düşürün (örn: 0.003).
                             # Eğer çok fazla gürültü alıyorsa, bu değeri artırın (örn: 0.008).

SILENCE_DURATION_S = 1.5     # Kaydı bitirmek için gereken sürekli sessizlik süresi (saniye).

# --- WHISPER MODEL AYARLARI ---
MODEL_SIZE = "small"
DEVICE = "cpu"
COMPUTE_TYPE = "int8"
