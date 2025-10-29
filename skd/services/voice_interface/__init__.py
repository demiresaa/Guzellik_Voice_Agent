# services/voice_interface/__init__.py

"""
Voice Interface Service
Sesli konuşma transkripsiyon ve LLM entegrasyonu
"""

from .transcriber import VoiceTranscriber
from .config import (
    SAMPLE_RATE,
    CHANNELS,
    MIN_AUDIO_LEVEL,
    SILENCE_DURATION_S,
    MODEL_SIZE,
    DEVICE,
    COMPUTE_TYPE
)

__all__ = [
    'VoiceTranscriber',
    'SAMPLE_RATE',
    'CHANNELS',
    'MIN_AUDIO_LEVEL',
    'SILENCE_DURATION_S',
    'MODEL_SIZE',
    'DEVICE',
    'COMPUTE_TYPE'
]
