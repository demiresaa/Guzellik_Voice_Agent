"""
shared/speech_to_text/example.py

Example usage of Speech-to-Text module

This file demonstrates various use cases for the STT module.
"""

import asyncio
from pathlib import Path

from shared.speech_to_text import (
    get_stt_provider,
    TranscriptionRequest,
    STTProviderFactory,
    STTSettings
)
from shared.common.logging import get_logger

logger = get_logger(__name__)


async def example_basic_transcription():
    """Example: Basic transcription from file."""
    print("\n" + "="*60)
    print("Example 1: Basic Transcription")
    print("="*60)

    # Get default provider (configured via environment)
    stt = get_stt_provider()

    # Create transcription request
    request = TranscriptionRequest(
        audio_path="path/to/audio.wav",
        language="tr"  # Turkish
    )

    try:
        # Transcribe
        response = await stt.transcribe(request)

        # Print results
        print(f"\nTranscribed Text: {response.text}")
        print(f"Language: {response.language}")
        print(f"Duration: {response.duration}s")
        print(f"Processing Time: {response.processing_time:.2f}s")
        print(f"Provider: {response.provider}")
        print(f"Model: {response.model}")

        # Print segments if available
        if response.segments:
            print("\nSegments:")
            for seg in response.segments[:3]:  # First 3 segments
                print(f"  [{seg.start:.2f}s - {seg.end:.2f}s]: {seg.text}")

    except Exception as e:
        logger.error(f"Transcription failed: {e}")


async def example_transcribe_bytes():
    """Example: Transcribe audio from bytes."""
    print("\n" + "="*60)
    print("Example 2: Transcribe from Bytes")
    print("="*60)

    # Read audio file
    audio_path = Path("path/to/audio.mp3")
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    print(f"Audio size: {len(audio_data)} bytes")

    # Get provider
    stt = get_stt_provider()

    # Transcribe from bytes
    request = TranscriptionRequest(
        audio_data=audio_data,
        language="auto"  # Auto-detect language
    )

    response = await stt.transcribe(request)
    print(f"\nTranscribed: {response.text}")
    print(f"Detected Language: {response.language}")


async def example_multiple_providers():
    """Example: Use multiple providers with fallback."""
    print("\n" + "="*60)
    print("Example 3: Multiple Providers with Fallback")
    print("="*60)

    # Configure settings
    settings = STTSettings(
        STT_PROVIDER="openai",
        STT_FALLBACK_ENABLED=True,
        STT_FALLBACK_PROVIDER="faster-whisper",
        OPENAI_API_KEY="your-api-key-here"
    )

    # Get primary and fallback providers
    primary = STTProviderFactory.get_primary_provider(settings)
    fallback = STTProviderFactory.get_fallback_provider(settings)

    print(f"Primary Provider: {primary.provider_name}")
    print(f"Fallback Provider: {fallback.provider_name if fallback else 'None'}")

    # Create request
    request = TranscriptionRequest(
        audio_path="path/to/audio.wav",
        language="tr"
    )

    # Try primary, fallback on failure
    try:
        print("\nTrying primary provider...")
        response = await primary.transcribe(request)
        print(f"Success with {response.provider}: {response.text[:50]}...")

    except Exception as e:
        logger.warning(f"Primary failed: {e}")

        if fallback:
            print("\nFalling back to secondary provider...")
            try:
                response = await fallback.transcribe(request)
                print(f"Success with {response.provider}: {response.text[:50]}...")
            except Exception as e:
                logger.error(f"Fallback also failed: {e}")


async def example_health_checks():
    """Example: Check provider health."""
    print("\n" + "="*60)
    print("Example 4: Health Checks")
    print("="*60)

    # Get provider
    stt = get_stt_provider()

    # Perform health check
    health = await stt.health_check()

    print(f"\nProvider: {health.provider}")
    print(f"Healthy: {health.is_healthy}")
    print(f"Response Time: {health.response_time_ms:.2f}ms")

    if health.model_loaded is not None:
        print(f"Model Loaded: {health.model_loaded}")

    if health.api_reachable is not None:
        print(f"API Reachable: {health.api_reachable}")

    if health.last_error:
        print(f"Last Error: {health.last_error}")


async def example_custom_options():
    """Example: Use custom transcription options."""
    print("\n" + "="*60)
    print("Example 5: Custom Transcription Options")
    print("="*60)

    stt = get_stt_provider()

    # Advanced options
    request = TranscriptionRequest(
        audio_path="path/to/audio.wav",
        language="tr",
        prompt="Randevu, güzellik merkezi, saç kesimi",  # Context hint
        temperature=0.0  # Deterministic (no randomness)
    )

    response = await stt.transcribe(request)
    print(f"\nTranscribed: {response.text}")


async def example_batch_transcription():
    """Example: Batch transcribe multiple files."""
    print("\n" + "="*60)
    print("Example 6: Batch Transcription")
    print("="*60)

    stt = get_stt_provider()

    # Multiple audio files
    audio_files = [
        "audio1.wav",
        "audio2.mp3",
        "audio3.m4a"
    ]

    results = []

    for audio_file in audio_files:
        print(f"\nTranscribing {audio_file}...")

        request = TranscriptionRequest(
            audio_path=audio_file,
            language="tr"
        )

        try:
            response = await stt.transcribe(request)
            results.append({
                "file": audio_file,
                "text": response.text,
                "success": True
            })
            print(f"✓ Success: {response.text[:50]}...")

        except Exception as e:
            results.append({
                "file": audio_file,
                "error": str(e),
                "success": False
            })
            print(f"✗ Failed: {e}")

    # Summary
    print("\n" + "-"*60)
    print(f"Total: {len(audio_files)}")
    print(f"Success: {sum(1 for r in results if r['success'])}")
    print(f"Failed: {sum(1 for r in results if not r['success'])}")


async def example_error_handling():
    """Example: Comprehensive error handling."""
    print("\n" + "="*60)
    print("Example 7: Error Handling")
    print("="*60)

    from shared.speech_to_text.exceptions import (
        AudioValidationException,
        AudioTooLargeException,
        UnsupportedAudioFormatException,
        TranscriptionException,
        ProviderUnavailableException
    )

    stt = get_stt_provider()

    request = TranscriptionRequest(
        audio_path="path/to/large_audio.wav",
        language="tr"
    )

    try:
        response = await stt.transcribe(request)
        print(f"Success: {response.text}")

    except AudioTooLargeException as e:
        print(f"✗ File too large:")
        print(f"  Size: {e.details['size_mb']:.2f}MB")
        print(f"  Max: {e.details['max_size_mb']:.2f}MB")

    except UnsupportedAudioFormatException as e:
        print(f"✗ Unsupported format:")
        print(f"  Format: {e.details['provided_format']}")
        print(f"  Supported: {', '.join(e.details['supported_formats'])}")

    except AudioValidationException as e:
        print(f"✗ Validation failed: {e.message}")

    except ProviderUnavailableException as e:
        print(f"✗ Provider unavailable: {e.details['provider']}")
        if 'retry_after_seconds' in e.details:
            print(f"  Retry after: {e.details['retry_after_seconds']}s")

    except TranscriptionException as e:
        print(f"✗ Transcription failed: {e.message}")
        print(f"  Provider: {e.details.get('provider')}")
        print(f"  Error: {e.details.get('original_error')}")

    except Exception as e:
        print(f"✗ Unexpected error: {e}")


async def example_with_metrics():
    """Example: Track metrics during transcription."""
    print("\n" + "="*60)
    print("Example 8: Metrics Tracking")
    print("="*60)

    from shared.speech_to_text.metrics import (
        record_transcription,
        record_provider_health
    )

    stt = get_stt_provider()

    # Check and record health
    health = await stt.health_check()
    record_provider_health(health.provider, health.is_healthy)

    # Transcribe with metrics
    request = TranscriptionRequest(
        audio_path="path/to/audio.wav",
        language="tr"
    )

    import time
    start = time.time()

    try:
        response = await stt.transcribe(request)
        duration = time.time() - start

        # Record metrics
        record_transcription(
            provider=response.provider,
            language=response.language,
            duration=duration,
            audio_duration=response.duration,
            success=True
        )

        print(f"✓ Transcription successful")
        print(f"  Processing time: {duration:.2f}s")

    except Exception as e:
        duration = time.time() - start

        # Record failure
        record_transcription(
            provider=stt.provider_name,
            language="tr",
            duration=duration,
            success=False
        )

        print(f"✗ Transcription failed: {e}")


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("Speech-to-Text Module - Examples")
    print("="*60)

    # Run examples
    examples = [
        ("Basic Transcription", example_basic_transcription),
        ("Transcribe Bytes", example_transcribe_bytes),
        ("Multiple Providers", example_multiple_providers),
        ("Health Checks", example_health_checks),
        ("Custom Options", example_custom_options),
        ("Batch Transcription", example_batch_transcription),
        ("Error Handling", example_error_handling),
        ("Metrics Tracking", example_with_metrics),
    ]

    for name, example_func in examples:
        try:
            await example_func()
        except Exception as e:
            logger.error(f"Example '{name}' failed: {e}")

    print("\n" + "="*60)
    print("Examples completed!")
    print("="*60)


if __name__ == "__main__":
    # Run examples
    asyncio.run(main())
