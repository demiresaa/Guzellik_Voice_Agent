# 🎤 Quick Start Guide - Real-Time Voice Assistant

**Complete guide to run the AI Voice Assistant system from scratch.**

## 📋 Prerequisites Checklist

- [ ] Python 3.10 or higher installed
- [ ] PostgreSQL installed and running
- [ ] Redis installed and running
- [ ] Git repository cloned
- [ ] Gemini API key obtained
- [ ] (Optional) OpenAI API key for fallback

## 🚀 Step-by-Step Setup

### Step 1: Install Dependencies

```bash
# Navigate to project root
cd Guzellik_Voice_Agent

# Install all dependencies
pip install -r requirements.txt
```

**Expected time:** 2-3 minutes

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit configuration
notepad .env  # or your preferred editor
```

**Required settings:**

```bash
# Add your API keys
GEMINI_API_KEY=your_gemini_api_key_here
OPENAI_API_KEY=your_openai_key_here  # optional

# Database (check if PostgreSQL is running)
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/guzellik_booking

# Redis (check if Redis is running)
REDIS_URL=redis://localhost:6379/0

# STT Configuration
STT_PROVIDER=faster-whisper
FASTER_WHISPER_MODEL=base
FASTER_WHISPER_DEVICE=auto

# Services URLs
BOOKING_AGENT_URL=http://localhost:8001
CONVERSATION_AGENT_URL=http://localhost:8002
VOICE_INTERFACE_URL=http://localhost:8000
```

### Step 3: Verify Services

#### Check PostgreSQL

```bash
# Test connection
psql -U postgres -h localhost

# Create database if needed
CREATE DATABASE guzellik_booking;
```

#### Check Redis

```bash
# Test connection
redis-cli ping
# Should respond: PONG
```

### Step 4: Start Services (In Order)

**Important:** Start services in separate terminal windows in this order:

#### Terminal 1: Booking Agent Service

```bash
cd services/booking_agent_service
python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8001
```

**Verify:** http://localhost:8001/health

#### Terminal 2: Conversation Agent Service

```bash
cd services/conversation_agent_service
python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8002
```

**Verify:** http://localhost:8002/health

#### Terminal 3: Voice Interface Service

```bash
cd services/voice_interface_service
python main.py
```

**Expected output:**
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Loading Faster-Whisper model: base
INFO:     Faster-Whisper model loaded successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**Note:** First run will download Faster-Whisper model (~500MB), may take 2-5 minutes.

**Verify:** http://localhost:8000/health

### Step 5: Test Voice Interface

1. **Open Web UI**
   - Navigate to: http://localhost:8000
   - You should see the voice assistant interface

2. **Grant Microphone Permission**
   - Click the microphone button
   - Browser will ask for microphone permission
   - Click "Allow"

3. **Test Conversation**
   - Click microphone button (turns red when active)
   - Speak: "Merhaba, yarın saat 14:00'te randevu almak istiyorum"
   - Watch real-time transcription appear
   - Wait for AI response

**Expected behavior:**
```
1. Your speech → "Merhaba, yarın..." (appears in real-time)
2. Final transcription → "Merhaba, yarın saat 14:00'te randevu almak istiyorum"
3. AI Response → "Merhaba! Tabii, yarın saat 14:00 için randevunuzu oluşturdum..."
```

## 🔍 Verification Checklist

### All Services Running

```bash
# Check all services
curl http://localhost:8001/health  # Booking Agent
curl http://localhost:8002/health  # Conversation Agent
curl http://localhost:8000/health  # Voice Interface
```

**All should return:**
```json
{
  "service": "...",
  "status": "healthy",
  "checks": { ... }
}
```

### Database Connected

```bash
# Check if database has tables
psql -U postgres -d guzellik_booking -c "\dt"
```

### Redis Connected

```bash
# Check Redis keys
redis-cli keys "*"
```

### STT Model Loaded

```bash
# Check Voice Interface health
curl http://localhost:8000/health | jq '.checks.stt.model_loaded'
# Should return: true
```

## 🎯 Test Scenarios

### Scenario 1: Simple Appointment

**Say:** "Yarın saat 15:00'te randevu almak istiyorum"

**Expected flow:**
1. Speech transcribed in real-time
2. Sent to conversation agent
3. Agent asks for phone number
4. You provide phone number
5. Agent confirms appointment

### Scenario 2: Customer Lookup

**Say:** "Telefon numaram 05321234567, randevu durumumu öğrenmek istiyorum"

**Expected flow:**
1. Speech transcribed
2. Customer looked up by phone
3. Agent provides appointment information

### Scenario 3: Service Inquiry

**Say:** "Hangi hizmetleriniz var?"

**Expected flow:**
1. Speech transcribed
2. Agent lists available services
3. Agent asks which service you prefer

## 🐛 Troubleshooting

### Issue: "Cannot connect to PostgreSQL"

**Solution:**
```bash
# Start PostgreSQL
# Windows:
pg_ctl start -D "C:\Program Files\PostgreSQL\14\data"

# Linux/Mac:
sudo service postgresql start
```

### Issue: "Cannot connect to Redis"

**Solution:**
```bash
# Start Redis
# Windows: (if using WSL)
redis-server

# Linux/Mac:
sudo service redis-server start
```

### Issue: "Faster-Whisper model download fails"

**Solution:**
```bash
# Download manually
python -c "from faster_whisper import WhisperModel; WhisperModel('base')"
```

### Issue: "Microphone not working"

**Solution:**
1. Check browser permissions (Settings → Privacy → Microphone)
2. Try different browser (Chrome recommended)
3. Check system microphone settings
4. Use HTTPS (required in production)

### Issue: "No transcription appearing"

**Check:**
1. VAD threshold may be too high:
   ```bash
   # In .env, try lowering:
   VAD_THRESHOLD=0.01
   ```
2. Microphone input level
3. Background noise (use quiet environment)

### Issue: "Conversation agent not responding"

**Check:**
1. Conversation Agent service is running (port 8002)
2. Check logs:
   ```bash
   cd services/voice_interface_service
   tail -f logs/voice-interface.log
   ```
3. Verify Gemini API key is valid

## 📊 Monitoring

### View Logs (Real-Time)

```bash
# Voice Interface logs
cd services/voice_interface_service
tail -f logs/*.log

# Conversation Agent logs
cd services/conversation_agent_service
tail -f logs/*.log

# Booking Agent logs
cd services/booking_agent_service
tail -f logs/*.log
```

### Check Metrics

```bash
# Voice Interface metrics
curl http://localhost:8000/metrics

# Active connections
curl http://localhost:8000/health | jq '.checks.connections'

# Active sessions
curl http://localhost:8000/health | jq '.checks.sessions'
```

## 🎉 Success Criteria

You have successfully set up the voice assistant if:

- [ ] All 3 services are running (8000, 8001, 8002)
- [ ] All health checks return "healthy"
- [ ] Web UI loads at http://localhost:8000
- [ ] Microphone access granted
- [ ] Speech is transcribed in real-time
- [ ] AI responds to questions
- [ ] Conversation history is saved

## 🚀 Next Steps

### For Development

1. **Customize prompts**
   - Edit `services/conversation_agent_service/app/config.py`
   - Modify system prompt for your business

2. **Add new tools**
   - Create new tools in `services/booking_agent_service/api/routes/`
   - Register in conversation agent

3. **Improve UI**
   - Edit `services/voice_interface_service/static/index.html`
   - Add features (history, settings, etc.)

### For Production

1. **Setup HTTPS**
   - Use nginx reverse proxy
   - Obtain SSL certificate

2. **Deploy to cloud**
   - Use Docker containers
   - Deploy to Kubernetes

3. **Enable monitoring**
   - Setup Prometheus + Grafana
   - Configure alerting

## 📞 Support

If you encounter issues:

1. **Check logs** (see Monitoring section)
2. **Verify configuration** (.env file)
3. **Test each service individually** (health endpoints)
4. **Check this guide** for common issues

## 🎓 Understanding the System

### How Real-Time Works

```
User speaks → Browser captures audio (16kHz)
           → WebSocket sends chunks every 0.1s
           → Voice Service buffers audio
           → VAD detects speech/silence
           → Speech segment extracted
           → Faster-Whisper transcribes
           → Partial results sent back
           → Final text sent to LLM
           → Response streamed back
```

### Architecture Overview

```
┌─────────────┐
│   Browser   │ Port 8000 (WebSocket)
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ Voice Interface │ Port 8000
│   - STT Stream  │
│   - VAD         │
│   - Sessions    │
└──────┬──────────┘
       │ HTTP
       ▼
┌──────────────────┐
│ Conversation     │ Port 8002
│   - Gemini LLM   │
│   - Context      │
└──────┬───────────┘
       │ HTTP
       ▼
┌──────────────────┐
│ Booking Agent    │ Port 8001
│   - 9 Tools      │
│   - Database     │
└──────────────────┘
```

---

**Ready to start?** Jump to [Step 1: Install Dependencies](#step-1-install-dependencies)

**Questions?** Check [Troubleshooting](#-troubleshooting) section

**Version:** 1.0.0
**Last Updated:** 2025-10-29
