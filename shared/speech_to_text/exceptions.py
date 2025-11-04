"""
shared/speech_to_text/exceptions.py

Speech-to-Text Specific Exceptions

Custom exceptions for STT operations with detailed error context.
"""

from typing import Optional, Dict, Any
from shared.common.exceptions import BaseAppException, ValidationException
from fastapi import status


class STTException(BaseAppException):
    """
    Base exception for all Speech-to-Text errors.

    Inherits from BaseAppException for consistent error handling.
    """

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_code: str = "STT_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            message=message,
            status_code=status_code,
            error_code=error_code,
            details=details
        )


class AudioValidationException(STTException):
    """
    Audio file validation error (400 Bad Request).

    Raised when audio file is invalid:
    - Unsupported format
    - Invalid MIME type
    - Corrupted file
    """

    def __init__(
        self,
        message: str = "Audio file validation failed",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if field:
            error_details["field"] = field

        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="AUDIO_VALIDATION_ERROR",
            details=error_details
        )


class AudioTooLargeException(STTException):
    """
    Audio file size exceeds limit (413 Payload Too Large).

    Raised when audio file exceeds maximum size.
    """

    def __init__(
        self,
        size_bytes: int,
        max_size_bytes: int,
        message: Optional[str] = None
    ):
        if message is None:
            size_mb = size_bytes / (1024 * 1024)
            max_mb = max_size_bytes / (1024 * 1024)
            message = f"Audio file too large: {size_mb:.2f}MB (max: {max_mb:.2f}MB)"

        super().__init__(
            message=message,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            error_code="AUDIO_TOO_LARGE",
            details={
                "size_bytes": size_bytes,
                "max_size_bytes": max_size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2),
                "max_size_mb": round(max_size_bytes / (1024 * 1024), 2)
            }
        )


class UnsupportedAudioFormatException(STTException):
    """
    Unsupported audio format (415 Unsupported Media Type).

    Raised when audio format is not supported by the provider.
    """

    def __init__(
        self,
        format: str,
        supported_formats: list[str],
        message: Optional[str] = None
    ):
        if message is None:
            message = f"Unsupported audio format: '{format}'"

        super().__init__(
            message=message,
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            error_code="UNSUPPORTED_AUDIO_FORMAT",
            details={
                "provided_format": format,
                "supported_formats": supported_formats
            }
        )


class TranscriptionException(STTException):
    """
    Transcription failed (500 Internal Server Error).

    Raised when transcription process fails.
    """

    def __init__(
        self,
        message: str = "Transcription failed",
        provider: Optional[str] = None,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        error_details = details or {}
        if provider:
            error_details["provider"] = provider
        if original_error:
            error_details["original_error"] = str(original_error)
            error_details["error_type"] = type(original_error).__name__

        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="TRANSCRIPTION_FAILED",
            details=error_details
        )


class ProviderUnavailableException(STTException):
    """
    STT provider unavailable (503 Service Unavailable).

    Raised when STT provider is down or unreachable.
    """

    def __init__(
        self,
        provider: str,
        message: Optional[str] = None,
        retry_after: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"STT provider '{provider}' is unavailable"

        error_details = details or {}
        error_details["provider"] = provider
        if retry_after:
            error_details["retry_after_seconds"] = retry_after

        super().__init__(
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_code="PROVIDER_UNAVAILABLE",
            details=error_details
        )


class ModelNotLoadedException(STTException):
    """
    STT model not loaded (500 Internal Server Error).

    Raised when faster-whisper model fails to load.
    """

    def __init__(
        self,
        model_name: str,
        message: Optional[str] = None,
        original_error: Optional[Exception] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        if message is None:
            message = f"Failed to load STT model: '{model_name}'"

        error_details = details or {}
        error_details["model_name"] = model_name
        if original_error:
            error_details["original_error"] = str(original_error)

        super().__init__(
            message=message,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="MODEL_NOT_LOADED",
            details=error_details
        )


class InvalidLanguageException(STTException):
    """
    Invalid language code (400 Bad Request).

    Raised when language code is not supported.
    """

    def __init__(
        self,
        language: str,
        supported_languages: Optional[list[str]] = None,
        message: Optional[str] = None
    ):
        if message is None:
            message = f"Unsupported language: '{language}'"

        error_details: Dict[str, Any] = {"provided_language": language}
        if supported_languages:
            error_details["supported_languages"] = supported_languages

        super().__init__(
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_LANGUAGE",
            details=error_details
        )


# Convenience functions

def audio_too_large(size_bytes: int, max_size_bytes: int) -> AudioTooLargeException:
    """Create AudioTooLargeException with size info."""
    return AudioTooLargeException(size_bytes, max_size_bytes)


def unsupported_format(format: str, supported: list[str]) -> UnsupportedAudioFormatException:
    """Create UnsupportedAudioFormatException with format info."""
    return UnsupportedAudioFormatException(format, supported)


def transcription_failed(
    provider: str,
    error: Optional[Exception] = None
) -> TranscriptionException:
    """Create TranscriptionException for failed transcription."""
    return TranscriptionException(provider=provider, original_error=error)


def provider_unavailable(
    provider: str,
    retry_after: Optional[int] = None
) -> ProviderUnavailableException:
    """Create ProviderUnavailableException for unavailable provider."""
    return ProviderUnavailableException(provider, retry_after=retry_after)
