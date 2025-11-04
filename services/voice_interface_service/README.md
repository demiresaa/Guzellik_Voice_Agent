# Voice Interface Service - Real-Time AI Voice Assistant

🎤 **Enterprise-grade real-time voice interface** for AI-powered conversations.

## 🎯 Features

- **Real-Time Speech-to-Text**: Streaming transcription with Faster-Whisper
- **Live Conversation**: Integrated with Conversation Agent (Gemini)
- **WebSocket Communication**: Low-latency bidirectional streaming
- **Voice Activity Detection**: Automatic speech detection and segmentation
- **Session Management**: Multi-user support with session tracking
- **Web UI**: Beautiful, responsive web interface
- **Production Ready**: Full observability, error handling, and resilience

## 🏗️ Architecture

```
┌─────────────┐      WebSocket        ┌──────────────────────┐
│   Browser   │ ←──────────────────→  │  Voice Service       │
│  Microphone │    Audio Chunks       │  (Port 8000)         │
└─────────────┘                        └──────────────────────┘
                                              ↓
                                       ┌──────────────────────┐
                                       │  STT Streaming       │
                                       │  (Faster-Whisper)    │
                                       └──────────────────────┘
                                              ↓
                                       ┌──────────────────────┐
                                       │ Conversation Agent   │
                                       │ (Port 8002)          │
                                       └──────────────────────┘
                                              ↓
                                       ┌──────────────────────┐
                                       │ Booking Agent        │
                                       │ (Port 8001)          │
                                       └──────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.10+**
2. **Faster-Whisper Model** (downloads automatically)
3. **Conversation Agent Service** (running on port 8002)
4. **PostgreSQL** (for conversation history)
5. **Redis** (for session management)

### Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your settings

# 3. Start services (in order)
# Terminal 1: Booking Agent
cd services/booking_agent_service
python main.py

# Terminal 2: Conversation Agent
cd services/conversation_agent_service
python main.py

# Terminal 3: Voice Interface (THIS SERVICE)
cd services/voice_interface_service
python main.py
```

### Access

Open browser: **http://localhost:8000**

## 📝 Configuration

### Environment Variables

```bash
# Service
SERVICE_PORT=8000
ENVIRONMENT=development

# Conversation Agent
CONVERSATION_AGENT_URL=http://localhost:8002

# Audio Settings
AUDIO_SAMPLE_RATE=16000
AUDIO_CHUNK_SIZE=4096

# STT Provider
STT_PROVIDER=faster-whisper
STT_LANGUAGE=tr

# VAD (Voice Activity Detection)
VAD_ENABLED=true
VAD_THRESHOLD=0.02
VAD_MIN_SPEECH_MS=250
VAD_MIN_SILENCE_MS=500

# Session
SESSION_TIMEOUT_SECONDS=300
MAX_CONCURRENT_SESSIONS=100

# Security
API_KEY=your-api-key-here
RATE_LIMIT_PER_MINUTE=100

# CORS
ALLOWED_ORIGINS=["http://localhost:3000","http://localhost:8000"]
```

## 🔄 How It Works

### 1. Connection Flow

```
1. User opens web UI
2. Browser requests microphone access
3. WebSocket connection established
4. Server creates voice session
5. Client ready to stream audio
```

### 2. Audio Streaming Flow

```
1. User speaks into microphone
2. Browser captures audio (16kHz, mono)
3. Audio chunked (4096 bytes)
4. Chunks sent via WebSocket (base64)
5. Server processes with VAD
6. Speech segments detected
7. STT streaming transcription
8. Partial results sent to client
```

### 3. Transcription Flow

```
1. Audio segment completed (silence detected)
2. Faster-Whisper transcribes segment
3. Interim results sent to client (real-time)
4. Final result sent when complete
5. Final text sent to Conversation Agent
6. LLM generates response
7. Response sent to client
8. Cycle repeats
```

## 🎯 WebSocket Protocol

### Client → Server

#### Start Session
```json
{
  "type": "start_session",
  "language": "tr",
  "phone_number": "05321234567",
  "metadata": {}
}
```

#### Audio Chunk
```json
{
  "type": "audio_chunk",
  "data": "base64_encoded_audio",
  "sequence": 123,
  "timestamp": 1234567890
}
```

#### End Session
```json
{
  "type": "end_session",
  "session_id": "session-uuid"
}
```

### Server → Client

#### Status
```json
{
  "type": "status",
  "status": "listening",
  "message": "Ready to receive audio",
  "metadata": {
    "session_id": "session-uuid"
  }
}
```

#### Transcription (Interim)
```json
{
  "type": "transcription_interim",
  "text": "Yarın saat...",
  "is_final": false,
  "confidence": 0.95,
  "language": "tr",
  "sequence": 5
}
```

#### Transcription (Final)
```json
{
  "type": "transcription_final",
  "text": "Yarın saat 14:00'te randevu almak istiyorum",
  "is_final": true,
  "confidence": 0.98,
  "language": "tr",
  "sequence": 6
}
```

#### Conversation Response
```json
{
  "type": "conversation_response",
  "text": "Tabii, yarın saat 14:00 için randevunuzu oluşturdum.",
  "session_id": "session-uuid",
  "action": "appointment_created"
}
```

#### Error
```json
{
  "type": "error",
  "error_code": "TRANSCRIPTION_ERROR",
  "error_message": "Transcription failed",
  "details": {}
}
```

## 📊 Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

```json
{
  "service": "voice-interface-service",
  "version": "1.0.0",
  "status": "healthy",
  "checks": {
    "stt": {
      "provider": "faster-whisper",
      "healthy": true,
      "model_loaded": true
    },
    "connections": {
      "active": 3,
      "max": 100
    },
    "sessions": {
      "active": 3
    }
  }
}
```

### Metrics

Available at `/metrics` (if Prometheus enabled):

- `voice_connections_total` - Total WebSocket connections
- `voice_sessions_active` - Active voice sessions
- `voice_transcriptions_total` - Total transcriptions
- `voice_errors_total` - Total errors

## 🧪 Testing

### Manual Test (Web UI)

1. Open http://localhost:8000
2. Click microphone button
3. Allow microphone access
4. Speak: "Yarın saat 14:00'te randevu almak istiyorum"
5. Watch real-time transcription
6. Receive AI response

### WebSocket Test (Python)

```python
import asyncio
import websockets
import json
import base64

async def test_voice():
    async with websockets.connect('ws://localhost:8000/ws/voice') as ws:
        # Start session
        await ws.send(json.dumps({
            'type': 'start_session',
            'language': 'tr'
        }))

        # Receive status
        message = await ws.recv()
        print(json.loads(message))

        # Send audio chunks
        with open('test_audio.wav', 'rb') as f:
            while chunk := f.read(4096):
                await ws.send(json.dumps({
                    'type': 'audio_chunk',
                    'data': base64.b64encode(chunk).decode(),
                    'sequence': 1
                }))
                await asyncio.sleep(0.01)

        # Receive transcriptions
        while True:
            message = await ws.recv()
            data = json.loads(message)
            print(f"[{data['type']}] {data.get('text', '')}")

asyncio.run(test_voice())
```

## 🔧 Troubleshooting

### Common Issues

**1. "WebSocket connection failed"**
- Check if service is running: `curl http://localhost:8000/health`
- Check firewall/network settings
- Verify CORS origins in config

**2. "Microphone access denied"**
- Browser security: requires HTTPS in production
- Check browser permissions
- Try different browser

**3. "STT model not loaded"**
- First run downloads model (~1GB)
- Check disk space
- Check internet connection

**4. "No transcription results"**
- Check VAD threshold (may be too high)
- Check audio format (must be 16kHz, mono)
- Check microphone input level

**5. "Conversation agent not responding"**
- Verify conversation agent is running (port 8002)
- Check `CONVERSATION_AGENT_URL` in config
- Check logs for HTTP errors

### Debug Mode

```bash
# Enable debug logging
LOG_LEVEL=DEBUG python main.py

# Check WebSocket messages
# Browser console → Network → WS → Messages
```

## 🏗️ Production Deployment

### Docker

```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python", "main.py"]
```

```bash
docker build -t voice-interface-service .
docker run -p 8000:8000 --env-file .env voice-interface-service
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: voice-interface
spec:
  replicas: 3
  selector:
    matchLabels:
      app: voice-interface
  template:
    metadata:
      labels:
        app: voice-interface
    spec:
      containers:
      - name: voice-interface
        image: voice-interface-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: ENVIRONMENT
          value: "production"
        resources:
          requests:
            memory: "2Gi"
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

### HTTPS (Production)

Use nginx as reverse proxy with SSL:

```nginx
server {
    listen 443 ssl http2;
    server_name voice.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📈 Performance

### Benchmarks

| Metric | Value |
|--------|-------|
| Latency (transcription) | ~500ms |
| Latency (full response) | ~2s |
| Concurrent sessions | 100+ |
| Audio chunk size | 4KB |
| WebSocket overhead | ~5% |

### Optimization Tips

1. **Use GPU for Faster-Whisper**: 5-10x faster
2. **Adjust VAD settings**: Balance latency vs accuracy
3. **Tune chunk size**: Larger = less overhead, more latency
4. **Use smaller model**: `tiny` for low latency, `base` for balance
5. **Enable caching**: For repeated queries

## 🔐 Security

- **HTTPS required in production**
- **API key authentication**
- **Rate limiting per IP**
- **CORS origin validation**
- **Input sanitization**
- **Session timeout**
- **Connection limits**

## 📚 API Reference

See [API.md](API.md) for detailed API documentation.

## 🤝 Contributing

1. Fork repository
2. Create feature branch
3. Make changes
4. Write tests
5. Submit pull request

## 📄 License

Internal use only. See LICENSE file.

## 🆘 Support

For issues or questions:
- Check logs (structured JSON)
- Check health endpoint
- Contact Staff Engineering Team

---

**Version:** 1.0.0
**Last Updated:** 2025-10-29
**Author:** Staff Engineering Team
