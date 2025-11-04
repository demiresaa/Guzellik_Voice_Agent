"""
shared/speech_to_text/metrics.py

Prometheus Metrics for Speech-to-Text

Tracks STT performance, usage, and errors for observability.
"""

from prometheus_client import Counter, Histogram, Gauge
from typing import Optional
import time
from functools import wraps

from shared.common.logging import get_logger

logger = get_logger(__name__)

# Transcription metrics
stt_transcriptions_total = Counter(
    "stt_transcriptions_total",
    "Total number of transcription requests",
    ["provider", "language", "status"]  # status: success, error, fallback
)

stt_transcription_duration_seconds = Histogram(
    "stt_transcription_duration_seconds",
    "Transcription processing time in seconds",
    ["provider"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

stt_audio_duration_seconds = Histogram(
    "stt_audio_duration_seconds",
    "Duration of audio files transcribed",
    ["provider"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0]
)

stt_audio_size_bytes = Histogram(
    "stt_audio_size_bytes",
    "Size of audio files in bytes",
    ["provider", "format"],
    buckets=[
        1024,        # 1KB
        10240,       # 10KB
        102400,      # 100KB
        1048576,     # 1MB
        5242880,     # 5MB
        10485760,    # 10MB
        26214400     # 25MB
    ]
)

# Provider health metrics
stt_provider_health = Gauge(
    "stt_provider_health",
    "Provider health status (1 = healthy, 0 = unhealthy)",
    ["provider"]
)

stt_model_loaded = Gauge(
    "stt_model_loaded",
    "Whether model is loaded (1 = loaded, 0 = not loaded)",
    ["provider", "model"]
)

# Error metrics
stt_errors_total = Counter(
    "stt_errors_total",
    "Total number of transcription errors",
    ["provider", "error_type"]
)

stt_validation_errors_total = Counter(
    "stt_validation_errors_total",
    "Total number of audio validation errors",
    ["error_type"]  # file_size, format, mime_type, path
)

# Cache metrics (if caching enabled)
stt_cache_hits_total = Counter(
    "stt_cache_hits_total",
    "Total number of cache hits",
    ["provider"]
)

stt_cache_misses_total = Counter(
    "stt_cache_misses_total",
    "Total number of cache misses",
    ["provider"]
)


def record_transcription(
    provider: str,
    language: Optional[str],
    duration: float,
    audio_duration: Optional[float] = None,
    audio_size: Optional[int] = None,
    audio_format: Optional[str] = None,
    success: bool = True,
    is_fallback: bool = False
):
    """
    Record transcription metrics.

    Args:
        provider: Provider name
        language: Language code
        duration: Processing time in seconds
        audio_duration: Audio duration in seconds
        audio_size: Audio size in bytes
        audio_format: Audio format
        success: Whether transcription succeeded
        is_fallback: Whether this was a fallback attempt
    """
    # Status
    status = "success" if success else "error"
    if is_fallback:
        status = "fallback"

    # Record counts
    stt_transcriptions_total.labels(
        provider=provider,
        language=language or "auto",
        status=status
    ).inc()

    # Record durations
    if success:
        stt_transcription_duration_seconds.labels(provider=provider).observe(duration)

        if audio_duration:
            stt_audio_duration_seconds.labels(provider=provider).observe(audio_duration)

        if audio_size and audio_format:
            stt_audio_size_bytes.labels(
                provider=provider,
                format=audio_format
            ).observe(audio_size)


def record_error(provider: str, error_type: str):
    """
    Record transcription error.

    Args:
        provider: Provider name
        error_type: Error type/class name
    """
    stt_errors_total.labels(
        provider=provider,
        error_type=error_type
    ).inc()


def record_validation_error(error_type: str):
    """
    Record audio validation error.

    Args:
        error_type: Validation error type
    """
    stt_validation_errors_total.labels(error_type=error_type).inc()


def record_provider_health(provider: str, is_healthy: bool):
    """
    Record provider health status.

    Args:
        provider: Provider name
        is_healthy: Health status
    """
    stt_provider_health.labels(provider=provider).set(1 if is_healthy else 0)


def record_model_loaded(provider: str, model: str, is_loaded: bool):
    """
    Record model loaded status.

    Args:
        provider: Provider name
        model: Model name
        is_loaded: Whether model is loaded
    """
    stt_model_loaded.labels(provider=provider, model=model).set(
        1 if is_loaded else 0
    )


def record_cache_hit(provider: str):
    """Record cache hit."""
    stt_cache_hits_total.labels(provider=provider).inc()


def record_cache_miss(provider: str):
    """Record cache miss."""
    stt_cache_misses_total.labels(provider=provider).inc()


def track_transcription_metrics(provider: str, language: Optional[str] = None):
    """
    Decorator to automatically track transcription metrics.

    Usage:
        ```python
        @track_transcription_metrics(provider="openai", language="tr")
        async def transcribe_file(...):
            ...
        ```
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False

            try:
                result = await func(*args, **kwargs)
                success = True

                # Extract metrics from result if available
                duration = time.time() - start_time
                audio_duration = getattr(result, "duration", None)

                record_transcription(
                    provider=provider,
                    language=language or getattr(result, "language", None),
                    duration=duration,
                    audio_duration=audio_duration,
                    success=True
                )

                return result

            except Exception as e:
                duration = time.time() - start_time

                record_transcription(
                    provider=provider,
                    language=language,
                    duration=duration,
                    success=False
                )

                record_error(provider, type(e).__name__)
                raise

        return wrapper
    return decorator
