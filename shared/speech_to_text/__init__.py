"""
shared/speech_to_text/__init__.py

Speech-to-Text Module

Provides enterprise-grade speech-to-text capabilities with:
- Multiple providers (OpenAI Whisper, Faster-Whisper)
- Automatic fallback
- Security validation
- Rate limiting
- Comprehensive error handling
- Observability (logging, metrics)

Quick Start:
    ```python
    from shared.speech_to_text import get_stt_provider, TranscriptionRequest

    # Get provider (configured via environment)
    stt = get_stt_provider()

    # Transcribe from file
    request = TranscriptionRequest(
        audio_path="/path/to/audio.wav",
        language="tr"
    )
    response = await stt.transcribe(request)
    print(response.text)
    ```

Configuration (Environment Variables):
    - STT_PROVIDER: "openai" or "faster-whisper" (default: faster-whisper)
    - STT_FALLBACK_ENABLED: Enable fallback (default: true)
    - OPENAI_API_KEY: OpenAI API key (required for OpenAI provider)
    - FASTER_WHISPER_MODEL: Model size (default: base)
    - STT_MAX_AUDIO_SIZE_MB: Max file size (default: 25MB)

Providers:
    - OpenAI Whisper: Cloud-based, high accuracy, costs per minute
    - Faster-Whisper: Local, no costs, privacy-focused

Security:
    - File size limits (25MB default)
    - Format whitelisting (wav, mp3, m4a, webm, ogg, flac)
    - MIME type verification
    - Path traversal protection
    - Rate limiting support
"""

# Version
__version__ = "1.0.0"

# Core components
from shared.speech_to_text.base import BaseSTTProvider
from shared.speech_to_text.factory import (
    STTProviderFactory,
    get_stt_provider
)
from shared.speech_to_text.config import STTSettings, get_stt_settings

# Schemas
from shared.speech_to_text.schemas import (
    TranscriptionRequest,
    TranscriptionResponse,
    TranscriptionSegment,
    AudioValidationResult,
    STTHealthCheck,
    AudioFormat,
    STTProvider,
    WhisperModel,
    Language
)

# Exceptions
from shared.speech_to_text.exceptions import (
    STTException,
    AudioValidationException,
    AudioTooLargeException,
    UnsupportedAudioFormatException,
    TranscriptionException,
    ProviderUnavailableException,
    ModelNotLoadedException,
    InvalidLanguageException
)

# Validators
from shared.speech_to_text.validators import (
    validate_audio_file,
    validate_audio_data,
    validate_file_path,
    validate_file_size,
    validate_audio_format
)

# Providers (for advanced usage)
from shared.speech_to_text.providers import (
    OpenAIWhisperProvider,
    FasterWhisperProvider
)

# Public API
__all__ = [
    # Version
    "__version__",

    # Main entry points
    "get_stt_provider",
    "STTProviderFactory",

    # Base class
    "BaseSTTProvider",

    # Providers
    "OpenAIWhisperProvider",
    "FasterWhisperProvider",

    # Configuration
    "STTSettings",
    "get_stt_settings",

    # Schemas
    "TranscriptionRequest",
    "TranscriptionResponse",
    "TranscriptionSegment",
    "AudioValidationResult",
    "STTHealthCheck",
    "AudioFormat",
    "STTProvider",
    "WhisperModel",
    "Language",

    # Exceptions
    "STTException",
    "AudioValidationException",
    "AudioTooLargeException",
    "UnsupportedAudioFormatException",
    "TranscriptionException",
    "ProviderUnavailableException",
    "ModelNotLoadedException",
    "InvalidLanguageException",

    # Validators
    "validate_audio_file",
    "validate_audio_data",
    "validate_file_path",
    "validate_file_size",
    "validate_audio_format",
]
