# Speech-to-Text Module

Enterprise-grade Speech-to-Text service with multiple provider support, automatic fallback, security validation, and comprehensive observability.

## Features

- **Multiple Providers**: OpenAI Whisper (cloud) and Faster-Whisper (local)
- **Automatic Fallback**: Seamless failover to secondary provider
- **Security First**: File validation, size limits, format whitelisting, path traversal protection
- **Observability**: Structured logging, Prometheus metrics, distributed tracing
- **Resilience**: Retry with exponential backoff, circuit breaker, graceful degradation
- **Performance**: Async/await, connection pooling, optional caching
- **Type Safety**: Full Pydantic schemas with validation

## Quick Start

### Basic Usage

```python
from shared.speech_to_text import get_stt_provider, TranscriptionRequest

# Get provider (configured via environment)
stt = get_stt_provider()

# Transcribe from file
request = TranscriptionRequest(
    audio_path="/path/to/audio.wav",
    language="tr"  # or "en", "auto"
)
response = await stt.transcribe(request)

print(response.text)  # Transcribed text
print(response.language)  # Detected/specified language
print(response.processing_time)  # Processing time in seconds
```

### Transcribe from Bytes

```python
# Read audio file
with open("audio.mp3", "rb") as f:
    audio_data = f.read()

# Transcribe
request = TranscriptionRequest(
    audio_data=audio_data,
    language="auto"
)
response = await stt.transcribe(request)
```

### Get Detailed Segments

```python
response = await stt.transcribe(request)

# Access segments with timing
for segment in response.segments:
    print(f"[{segment.start:.2f}s - {segment.end:.2f}s]: {segment.text}")
    print(f"Confidence: {segment.confidence:.2f}")
```

## Configuration

### Environment Variables

```bash
# Provider Selection
STT_PROVIDER=faster-whisper          # or "openai"
STT_FALLBACK_ENABLED=true
STT_FALLBACK_PROVIDER=openai         # Optional

# OpenAI Settings
OPENAI_API_KEY=sk-...
OPENAI_WHISPER_MODEL=whisper-1
OPENAI_TIMEOUT=30
OPENAI_MAX_RETRIES=3

# Faster-Whisper Settings
FASTER_WHISPER_MODEL=base            # tiny, base, small, medium, large-v2, large-v3
FASTER_WHISPER_DEVICE=auto           # cpu, cuda, auto
FASTER_WHISPER_COMPUTE_TYPE=auto     # int8, float16, float32, auto
FASTER_WHISPER_CPU_THREADS=4

# General Settings
STT_DEFAULT_LANGUAGE=auto            # auto, tr, en
STT_MAX_AUDIO_SIZE_MB=25
STT_CACHE_ENABLED=false
STT_ENABLE_VAD=true                  # Voice Activity Detection
```

### Programmatic Configuration

```python
from shared.speech_to_text import STTProviderFactory, STTSettings

# Custom settings
settings = STTSettings(
    STT_PROVIDER="openai",
    OPENAI_API_KEY="sk-...",
    STT_MAX_AUDIO_SIZE_MB=10
)

# Create provider with custom settings
provider = STTProviderFactory.create_provider("openai", settings)
```

## Providers

### OpenAI Whisper (Cloud)

**Pros:**
- High accuracy
- Fast processing (cloud compute)
- No local resources needed
- Automatic model updates

**Cons:**
- Requires API key (costs money)
- Network dependency
- Data leaves your infrastructure
- 25MB file size limit

**Use When:**
- You need highest accuracy
- You have internet connectivity
- You're okay with cloud processing
- You want zero maintenance

### Faster-Whisper (Local)

**Pros:**
- Free (no API costs)
- Privacy (data stays local)
- No network dependency
- GPU acceleration support

**Cons:**
- Requires local resources (CPU/GPU, RAM, disk)
- Model download on first use
- Slower on CPU (faster on GPU)
- Requires maintenance (model updates)

**Use When:**
- You need privacy/compliance
- You have local GPU
- You want zero API costs
- You process high volume

## Advanced Usage

### Custom Provider

```python
from shared.speech_to_text import BaseSTTProvider, TranscriptionResponse

class MyCustomProvider(BaseSTTProvider):
    async def initialize(self):
        # Initialize your provider
        pass

    async def transcribe_file(self, file_path, language, **kwargs):
        # Implement transcription
        return TranscriptionResponse(...)

    async def health_check(self):
        # Implement health check
        return STTHealthCheck(...)
```

### Fallback Strategy

```python
from shared.speech_to_text import STTProviderFactory

settings = STTSettings(
    STT_PROVIDER="openai",
    STT_FALLBACK_ENABLED=True,
    STT_FALLBACK_PROVIDER="faster-whisper"
)

primary = STTProviderFactory.get_primary_provider(settings)
fallback = STTProviderFactory.get_fallback_provider(settings)

try:
    response = await primary.transcribe(request)
except Exception as e:
    logger.warning("Primary failed, using fallback", extra={"error": str(e)})
    response = await fallback.transcribe(request)
```

### Health Checks

```python
# Check provider health
health = await stt.health_check()

print(f"Healthy: {health.is_healthy}")
print(f"Provider: {health.provider}")
print(f"Response time: {health.response_time_ms}ms")

if not health.is_healthy:
    print(f"Error: {health.last_error}")
```

## Security

### File Validation

All audio files are validated for:
- **File size**: Max 25MB (configurable)
- **Format**: Whitelisted formats only (wav, mp3, m4a, webm, ogg, flac)
- **MIME type**: Verified using python-magic
- **Path traversal**: Protected against directory traversal attacks

### Rate Limiting

Integrate with shared rate limiter:

```python
from shared.security.rate_limiter import rate_limit

@rate_limit(max_requests=10, window_seconds=60)
async def transcribe_endpoint(request):
    stt = get_stt_provider()
    return await stt.transcribe(request)
```

## Observability

### Structured Logging

```python
# Logs are automatically structured in JSON format
{
  "timestamp": "2025-10-29T12:34:56Z",
  "service": "stt",
  "level": "INFO",
  "provider": "openai",
  "action": "transcribe_file",
  "file": "/path/to/audio.wav",
  "processing_time": 1.234,
  "success": true
}
```

### Prometheus Metrics

```python
# Available metrics:
- stt_transcriptions_total{provider, language, status}
- stt_transcription_duration_seconds{provider}
- stt_audio_duration_seconds{provider}
- stt_audio_size_bytes{provider, format}
- stt_provider_health{provider}
- stt_errors_total{provider, error_type}
- stt_validation_errors_total{error_type}
```

### Manual Metrics

```python
from shared.speech_to_text.metrics import (
    record_transcription,
    record_error,
    record_provider_health
)

# Record custom metrics
record_transcription(
    provider="openai",
    language="tr",
    duration=1.5,
    audio_duration=10.0,
    success=True
)
```

## Error Handling

### Exception Hierarchy

```
BaseAppException (shared)
└── STTException
    ├── AudioValidationException
    │   ├── AudioTooLargeException
    │   └── UnsupportedAudioFormatException
    ├── TranscriptionException
    ├── ProviderUnavailableException
    ├── ModelNotLoadedException
    └── InvalidLanguageException
```

### Exception Handling

```python
from shared.speech_to_text.exceptions import (
    AudioValidationException,
    AudioTooLargeException,
    TranscriptionException,
    ProviderUnavailableException
)

try:
    response = await stt.transcribe(request)
except AudioTooLargeException as e:
    print(f"File too large: {e.details['size_mb']}MB")
except AudioValidationException as e:
    print(f"Invalid audio: {e.message}")
except ProviderUnavailableException as e:
    print(f"Provider down: {e.details['provider']}")
    print(f"Retry after: {e.details.get('retry_after_seconds')}s")
except TranscriptionException as e:
    print(f"Transcription failed: {e.message}")
```

## Performance

### Benchmarks

| Provider | Model | Device | Audio (10s) | Processing Time |
|----------|-------|--------|-------------|-----------------|
| OpenAI | whisper-1 | Cloud | 10s | ~1.5s |
| Faster-Whisper | tiny | CPU | 10s | ~3.0s |
| Faster-Whisper | base | CPU | 10s | ~5.0s |
| Faster-Whisper | base | GPU | 10s | ~0.8s |
| Faster-Whisper | small | GPU | 10s | ~1.2s |
| Faster-Whisper | medium | GPU | 10s | ~2.0s |

### Optimization Tips

1. **Use GPU for Faster-Whisper**: 5-10x faster than CPU
2. **Use smaller models**: `tiny` for real-time, `base` for balanced
3. **Enable VAD**: Skips silence, reduces processing time
4. **Enable caching**: For repeated audio (testing, demos)
5. **Use OpenAI for high volume**: Cloud scales better

## Testing

### Unit Tests

```python
import pytest
from shared.speech_to_text import get_stt_provider, TranscriptionRequest

@pytest.mark.asyncio
async def test_transcribe_file():
    stt = get_stt_provider()
    request = TranscriptionRequest(
        audio_path="tests/fixtures/sample.wav",
        language="en"
    )
    response = await stt.transcribe(request)
    assert response.text
    assert response.language == "en"
```

### Integration Tests

```bash
# Test with real audio
pytest tests/integration/test_stt.py -v

# Test specific provider
pytest tests/integration/test_stt.py::test_openai -v
pytest tests/integration/test_stt.py::test_faster_whisper -v
```

## Troubleshooting

### Common Issues

**1. "OPENAI_API_KEY is required"**
- Set `OPENAI_API_KEY` environment variable
- Or switch to `faster-whisper` provider

**2. "Model not loaded"**
- Faster-Whisper downloads model on first use
- Check internet connection
- Check disk space (~1-3GB per model)

**3. "Audio file too large"**
- Max size is 25MB by default
- Increase `STT_MAX_AUDIO_SIZE_MB`
- Or compress audio file

**4. "Unsupported audio format"**
- Supported: wav, mp3, m4a, webm, ogg, flac, opus
- Convert to supported format using ffmpeg

**5. "CUDA out of memory"**
- Use smaller model (tiny, base)
- Switch to CPU: `FASTER_WHISPER_DEVICE=cpu`
- Use int8 compute: `FASTER_WHISPER_COMPUTE_TYPE=int8`

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=DEBUG python your_app.py

# Check provider health
python -m shared.speech_to_text.health_check
```

## Migration Guide

### From OpenAI Python Client

**Before:**
```python
from openai import OpenAI
client = OpenAI()

with open("audio.wav", "rb") as f:
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=f
    )
print(response.text)
```

**After:**
```python
from shared.speech_to_text import get_stt_provider, TranscriptionRequest

stt = get_stt_provider()
request = TranscriptionRequest(audio_path="audio.wav")
response = await stt.transcribe(request)
print(response.text)
```

### From faster-whisper

**Before:**
```python
from faster_whisper import WhisperModel

model = WhisperModel("base")
segments, info = model.transcribe("audio.wav")
text = " ".join([seg.text for seg in segments])
```

**After:**
```python
from shared.speech_to_text import get_stt_provider, TranscriptionRequest

stt = get_stt_provider()
request = TranscriptionRequest(audio_path="audio.wav")
response = await stt.transcribe(request)
text = response.text
```

## Dependencies

Required packages:
```
openai>=1.0.0
faster-whisper>=0.10.0
python-magic>=0.4.27
prometheus-client>=0.19.0
pydantic>=2.0.0
httpx>=0.25.0
```

## License

Internal use only. See LICENSE file.

## Support

For issues or questions:
1. Check logs (structured JSON format)
2. Check metrics (Prometheus /metrics endpoint)
3. Run health check
4. Contact Staff Engineering Team

---

**Version:** 1.0.0
**Last Updated:** 2025-10-29
**Author:** Staff Engineering Team
