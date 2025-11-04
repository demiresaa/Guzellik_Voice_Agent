"""
shared/speech_to_text/providers/__init__.py

STT Provider Implementations
"""

from .openai_whisper import OpenAIWhisperProvider
from .faster_whisper import FasterWhisperProvider

__all__ = ["OpenAIWhisperProvider", "FasterWhisperProvider"]
