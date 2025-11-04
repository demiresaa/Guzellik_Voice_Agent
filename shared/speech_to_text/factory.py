"""
shared/speech_to_text/factory.py

STT Provider Factory

Creates and manages STT provider instances using Factory pattern.
Supports provider selection, fallback, and singleton management.
"""

from typing import Optional, Dict
from functools import lru_cache

from shared.common.logging import get_logger
from shared.speech_to_text.base import BaseSTTProvider
from shared.speech_to_text.providers import OpenAIWhisperProvider, FasterWhisperProvider
from shared.speech_to_text.config import STTSettings, get_stt_settings
from shared.speech_to_text.exceptions import STTException

logger = get_logger(__name__)


class STTProviderFactory:
    """
    Factory for creating STT provider instances.

    Implements Factory pattern with singleton caching.
    Providers are created once and reused for efficiency.
    """

    _providers: Dict[str, BaseSTTProvider] = {}

    @classmethod
    def create_provider(
        cls,
        provider_name: str,
        settings: Optional[STTSettings] = None
    ) -> BaseSTTProvider:
        """
        Create or get cached STT provider instance.

        Args:
            provider_name: Provider name ("openai" or "faster-whisper")
            settings: Optional settings (uses default if not provided)

        Returns:
            Initialized STT provider instance

        Raises:
            ValueError: If provider name is invalid
            STTException: If provider creation fails
        """
        # Use default settings if not provided
        if settings is None:
            settings = get_stt_settings()

        # Check cache
        if provider_name in cls._providers:
            logger.debug(f"Returning cached {provider_name} provider")
            return cls._providers[provider_name]

        # Create new provider
        logger.info(f"Creating new {provider_name} provider")

        try:
            if provider_name == "openai":
                provider = cls._create_openai_provider(settings)
            elif provider_name == "faster-whisper":
                provider = cls._create_faster_whisper_provider(settings)
            else:
                raise ValueError(
                    f"Unknown STT provider: {provider_name}. "
                    f"Supported: 'openai', 'faster-whisper'"
                )

            # Cache provider
            cls._providers[provider_name] = provider

            logger.info(f"Provider {provider_name} created successfully")
            return provider

        except Exception as e:
            logger.error(
                f"Failed to create {provider_name} provider",
                extra={"error": str(e)}
            )
            raise STTException(
                message=f"Failed to create STT provider: {provider_name}",
                details={"error": str(e), "provider": provider_name}
            )

    @classmethod
    def _create_openai_provider(cls, settings: STTSettings) -> OpenAIWhisperProvider:
        """Create OpenAI Whisper provider."""
        return OpenAIWhisperProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_WHISPER_MODEL,
            timeout=settings.OPENAI_TIMEOUT,
            max_retries=settings.OPENAI_MAX_RETRIES
        )

    @classmethod
    def _create_faster_whisper_provider(cls, settings: STTSettings) -> FasterWhisperProvider:
        """Create Faster-Whisper provider."""
        return FasterWhisperProvider(
            model_size=settings.FASTER_WHISPER_MODEL,
            device=settings.FASTER_WHISPER_DEVICE,
            compute_type=settings.FASTER_WHISPER_COMPUTE_TYPE,
            cpu_threads=settings.FASTER_WHISPER_CPU_THREADS,
            num_workers=settings.FASTER_WHISPER_NUM_WORKERS
        )

    @classmethod
    def get_primary_provider(
        cls,
        settings: Optional[STTSettings] = None
    ) -> BaseSTTProvider:
        """
        Get primary STT provider based on configuration.

        Args:
            settings: Optional settings (uses default if not provided)

        Returns:
            Primary STT provider instance
        """
        if settings is None:
            settings = get_stt_settings()

        logger.debug(f"Getting primary provider: {settings.STT_PROVIDER}")
        return cls.create_provider(settings.STT_PROVIDER, settings)

    @classmethod
    def get_fallback_provider(
        cls,
        settings: Optional[STTSettings] = None
    ) -> Optional[BaseSTTProvider]:
        """
        Get fallback STT provider if enabled.

        Args:
            settings: Optional settings (uses default if not provided)

        Returns:
            Fallback STT provider instance or None if disabled
        """
        if settings is None:
            settings = get_stt_settings()

        if not settings.STT_FALLBACK_ENABLED:
            logger.debug("Fallback provider disabled")
            return None

        fallback_name = settings.STT_FALLBACK_PROVIDER
        if not fallback_name:
            # Auto-select fallback (opposite of primary)
            fallback_name = (
                "faster-whisper" if settings.STT_PROVIDER == "openai"
                else "openai"
            )

        logger.debug(f"Getting fallback provider: {fallback_name}")
        try:
            return cls.create_provider(fallback_name, settings)
        except Exception as e:
            logger.warning(
                f"Failed to create fallback provider: {fallback_name}",
                extra={"error": str(e)}
            )
            return None

    @classmethod
    async def cleanup_all(cls) -> None:
        """
        Cleanup all cached providers.

        Calls cleanup() on all providers and clears cache.
        Should be called on application shutdown.
        """
        logger.info("Cleaning up all STT providers")

        for provider_name, provider in cls._providers.items():
            try:
                await provider.cleanup()
                logger.debug(f"Provider {provider_name} cleaned up")
            except Exception as e:
                logger.error(
                    f"Error cleaning up provider {provider_name}",
                    extra={"error": str(e)}
                )

        cls._providers.clear()
        logger.info("All STT providers cleaned up")

    @classmethod
    def clear_cache(cls) -> None:
        """
        Clear provider cache without cleanup.

        Use cleanup_all() for proper resource cleanup.
        """
        cls._providers.clear()
        logger.debug("Provider cache cleared")


# Convenience function
@lru_cache()
def get_stt_provider() -> BaseSTTProvider:
    """
    Get the primary STT provider (cached).

    This is the main entry point for getting an STT provider.
    Uses configuration from environment variables.

    Returns:
        Primary STT provider instance

    Example:
        ```python
        from shared.speech_to_text import get_stt_provider

        stt = get_stt_provider()
        response = await stt.transcribe(request)
        ```
    """
    return STTProviderFactory.get_primary_provider()
