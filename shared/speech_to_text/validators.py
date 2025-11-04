"""
shared/speech_to_text/validators.py

Audio File Validation

Security-focused validation for audio files:
- File size limits
- Format whitelisting
- MIME type verification
- Path traversal protection
"""

import os
import magic  # python-magic for MIME type detection
from pathlib import Path
from typing import Optional, Tuple

from shared.common.logging import get_logger
from shared.speech_to_text.exceptions import (
    AudioValidationException,
    AudioTooLargeException,
    UnsupportedAudioFormatException
)
from shared.speech_to_text.schemas import AudioFormat, AudioValidationResult

logger = get_logger(__name__)

# Security constants
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024  # 25MB (OpenAI Whisper limit)
SUPPORTED_FORMATS = [fmt.value for fmt in AudioFormat]
SUPPORTED_MIME_TYPES = [
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/m4a",
    "audio/x-m4a",
    "audio/webm",
    "audio/ogg",
    "audio/opus",
    "audio/flac",
    "audio/x-flac",
]


def validate_file_path(file_path: str) -> Path:
    """
    Validate and sanitize file path.

    Args:
        file_path: Path to audio file

    Returns:
        Validated Path object

    Raises:
        AudioValidationException: If path is invalid or unsafe
    """
    try:
        path = Path(file_path).resolve()
    except (ValueError, OSError) as e:
        logger.error("Invalid file path", extra={"path": file_path, "error": str(e)})
        raise AudioValidationException(
            message="Invalid file path",
            field="audio_path",
            details={"error": str(e)}
        )

    # Check path traversal (after resolve, should not go outside expected dirs)
    path_str = str(path)
    if ".." in path_str or path_str.startswith("~"):
        logger.warning("Path traversal attempt detected", extra={"path": file_path})
        raise AudioValidationException(
            message="Invalid file path: path traversal detected",
            field="audio_path"
        )

    # Check if file exists
    if not path.exists():
        raise AudioValidationException(
            message=f"Audio file not found: {file_path}",
            field="audio_path"
        )

    # Check if it's a file (not directory)
    if not path.is_file():
        raise AudioValidationException(
            message=f"Path is not a file: {file_path}",
            field="audio_path"
        )

    return path


def validate_file_size(file_path: Path, max_size: int = MAX_AUDIO_SIZE_BYTES) -> int:
    """
    Validate file size.

    Args:
        file_path: Path to audio file
        max_size: Maximum allowed size in bytes

    Returns:
        File size in bytes

    Raises:
        AudioTooLargeException: If file exceeds size limit
    """
    size = file_path.stat().st_size

    if size > max_size:
        logger.warning(
            "Audio file too large",
            extra={
                "path": str(file_path),
                "size_bytes": size,
                "max_bytes": max_size
            }
        )
        raise AudioTooLargeException(size, max_size)

    if size == 0:
        raise AudioValidationException(
            message="Audio file is empty",
            field="audio_path"
        )

    return size


def validate_bytes_size(data: bytes, max_size: int = MAX_AUDIO_SIZE_BYTES) -> int:
    """
    Validate audio data size.

    Args:
        data: Audio data as bytes
        max_size: Maximum allowed size in bytes

    Returns:
        Data size in bytes

    Raises:
        AudioTooLargeException: If data exceeds size limit
    """
    size = len(data)

    if size > max_size:
        logger.warning(
            "Audio data too large",
            extra={"size_bytes": size, "max_bytes": max_size}
        )
        raise AudioTooLargeException(size, max_size)

    if size == 0:
        raise AudioValidationException(
            message="Audio data is empty",
            field="audio_data"
        )

    return size


def detect_audio_format(file_path: Path) -> Tuple[str, str]:
    """
    Detect audio format and MIME type.

    Args:
        file_path: Path to audio file

    Returns:
        Tuple of (format, mime_type)

    Raises:
        AudioValidationException: If format detection fails
    """
    try:
        # Detect MIME type using python-magic
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(str(file_path))

        # Extract format from extension (fallback)
        extension = file_path.suffix.lstrip(".").lower()

        logger.debug(
            "Audio format detected",
            extra={
                "path": str(file_path),
                "mime_type": mime_type,
                "extension": extension
            }
        )

        return extension, mime_type

    except Exception as e:
        logger.error(
            "Failed to detect audio format",
            extra={"path": str(file_path), "error": str(e)}
        )
        raise AudioValidationException(
            message="Failed to detect audio format",
            field="audio_path",
            details={"error": str(e)}
        )


def validate_audio_format(format: str, mime_type: str) -> None:
    """
    Validate audio format and MIME type.

    Args:
        format: File extension (e.g., "wav", "mp3")
        mime_type: MIME type (e.g., "audio/wav")

    Raises:
        UnsupportedAudioFormatException: If format is not supported
    """
    # Validate format
    if format not in SUPPORTED_FORMATS:
        logger.warning(
            "Unsupported audio format",
            extra={"format": format, "supported": SUPPORTED_FORMATS}
        )
        raise UnsupportedAudioFormatException(format, SUPPORTED_FORMATS)

    # Validate MIME type
    if mime_type not in SUPPORTED_MIME_TYPES:
        logger.warning(
            "Unsupported MIME type",
            extra={"mime_type": mime_type, "supported": SUPPORTED_MIME_TYPES}
        )
        raise AudioValidationException(
            message=f"Unsupported MIME type: {mime_type}",
            field="audio_path",
            details={"mime_type": mime_type, "supported": SUPPORTED_MIME_TYPES}
        )


def validate_audio_file(
    file_path: str,
    max_size: int = MAX_AUDIO_SIZE_BYTES
) -> AudioValidationResult:
    """
    Comprehensive audio file validation.

    Validates:
    1. Path safety (no traversal)
    2. File existence
    3. File size
    4. Audio format
    5. MIME type

    Args:
        file_path: Path to audio file
        max_size: Maximum allowed size in bytes

    Returns:
        AudioValidationResult with validation details

    Raises:
        AudioValidationException: If validation fails
        AudioTooLargeException: If file is too large
        UnsupportedAudioFormatException: If format is unsupported
    """
    errors = []

    try:
        # 1. Validate path
        path = validate_file_path(file_path)

        # 2. Validate size
        size = validate_file_size(path, max_size)

        # 3. Detect and validate format
        format, mime_type = detect_audio_format(path)
        validate_audio_format(format, mime_type)

        logger.info(
            "Audio file validation successful",
            extra={
                "path": file_path,
                "size_bytes": size,
                "format": format,
                "mime_type": mime_type
            }
        )

        return AudioValidationResult(
            is_valid=True,
            format=format,
            size_bytes=size,
            mime_type=mime_type,
            errors=[]
        )

    except (
        AudioValidationException,
        AudioTooLargeException,
        UnsupportedAudioFormatException
    ) as e:
        # Re-raise validation exceptions
        raise

    except Exception as e:
        # Catch unexpected errors
        logger.error(
            "Unexpected error during audio validation",
            extra={"path": file_path, "error": str(e)}
        )
        raise AudioValidationException(
            message="Audio validation failed",
            details={"error": str(e)}
        )


def validate_audio_data(
    data: bytes,
    max_size: int = MAX_AUDIO_SIZE_BYTES
) -> AudioValidationResult:
    """
    Validate audio data bytes.

    Args:
        data: Audio data as bytes
        max_size: Maximum allowed size in bytes

    Returns:
        AudioValidationResult with validation details

    Raises:
        AudioValidationException: If validation fails
        AudioTooLargeException: If data is too large
    """
    try:
        # Validate size
        size = validate_bytes_size(data, max_size)

        # Try to detect MIME type from data
        mime = magic.Magic(mime=True)
        mime_type = mime.from_buffer(data)

        logger.info(
            "Audio data validation successful",
            extra={"size_bytes": size, "mime_type": mime_type}
        )

        return AudioValidationResult(
            is_valid=True,
            size_bytes=size,
            mime_type=mime_type,
            errors=[]
        )

    except (AudioValidationException, AudioTooLargeException) as e:
        # Re-raise validation exceptions
        raise

    except Exception as e:
        # Catch unexpected errors
        logger.error(
            "Unexpected error during audio data validation",
            extra={"error": str(e)}
        )
        raise AudioValidationException(
            message="Audio data validation failed",
            details={"error": str(e)}
        )
