# Real-Time Voice Interface - Implementation Guide

## 🎯 Sistem Genel Bakış

Bu **Real-Time AI Voice Assistant** sistemidir. Kullanıcı konuşurken anlık olarak ses metne dönüşür, LLM ile işlenir ve yanıt verilir.

## 📊 Architecture

```
┌─────────────┐      WebSocket       ┌──────────────────┐
│   Browser   │ ←──────────────────→ │  Voice Service   │
│  Microphone │    Audio Chunks      │  (Port 8000)     │
└─────────────┘                       └──────────────────┘
                                             ↓
                                      ┌──────────────────┐
                                      │  STT Streaming   │
                                      │ (Faster-Whisper) │
                                      └──────────────────┘
                                             ↓
                                      ┌──────────────────┐
                                      │ Conversation     │
                                      │ Agent (Gemini)   │
                                      └──────────────────┘
```

## 🔄 Data Flow

### 1. User Konuşuyor

```
Browser → AudioChunk → WebSocket → Voice Service
                                   ↓
                            Audio Buffer (VAD)
                                   ↓
                            Speech Detected
                                   ↓
                            STT Streaming
                                   ↓
                            "Yarın saat..."
```

### 2. Transcription Real-Time

```javascript
// Browser sends audio
webSocket.send({
  type: "audio_chunk",
  data: base64Audio,
  sequence: 1
});

// Server responds IMMEDIATELY (partial)
← {
  type: "transcription_interim",
  text: "Yarın",
  is_final: false
}

← {
  type: "transcription_interim",
  text: "Yarın saat",
  is_final: false
}

← {
  type: "transcription_final",
  text: "Yarın saat 14:00'te randevu almak istiyorum",
  is_final: true
}
```

### 3. LLM Response

```
Transcription → Conversation Agent → Gemini LLM
                                    ↓
                              "Tabii, yarın..."
                                    ↓
                              WebSocket Response
```

## 🚀 Implementasyon Durumu

### ✅ Tamamlanan

1. **STT Infrastructure** (Batch + Streaming)
   - ✅ Base abstraction layer
   - ✅ Faster-Whisper provider (streaming support)
   - ✅ OpenAI Whisper provider (batch only)
   - ✅ Audio validation & security
   - ✅ Metrics & logging

2. **Streaming Infrastructure**
   - ✅ Audio buffer management
   - ✅ Voice Activity Detection (VAD)
   - ✅ Audio stream processor
   - ✅ Chunk handling

3. **Voice Service Structure**
   - ✅ Configuration
   - ✅ WebSocket message schemas
   - ✅ Service directory structure

### 🔨 Gerekli (Şu Anda Eksik)

4. **WebSocket Handler** (500+ LOC)
   - ❌ Connection management
   - ❌ Audio stream handling
   - ❌ Session management
   - ❌ Real-time transcription integration

5. **Voice Service Logic** (300+ LOC)
   - ❌ STT coordination
   - ❌ Conversation agent integration
   - ❌ Response streaming

6. **Web UI** (400+ LOC)
   - ❌ Microphone capture
   - ❌ WebSocket client
   - ❌ Real-time display
   - ❌ Audio visualization

7. **FastAPI App** (200+ LOC)
   - ❌ Server setup
   - ❌ WebSocket route
   - ❌ Health checks

## 🎯 Nasıl Çalışacak? (Final Implementation)

### Backend (Voice Service)

```python
# services/voice_interface_service/main.py
from fastapi import FastAPI, WebSocket
from shared.speech_to_text import get_stt_provider

app = FastAPI()
stt = get_stt_provider()  # Faster-Whisper with streaming

@app.websocket("/ws/voice")
async def voice_websocket(websocket: WebSocket):
    await websocket.accept()

    # Create audio stream
    async def audio_generator():
        while True:
            # Receive audio chunks from browser
            data = await websocket.receive_bytes()
            yield data

    # Start streaming transcription
    async for transcription in stt.transcribe_stream(
        audio_stream=audio_generator(),
        language="tr"
    ):
        # Send partial results to client
        await websocket.send_json({
            "type": "transcription",
            "text": transcription.text,
            "is_final": transcription.is_final
        })

        # If final, send to LLM
        if transcription.is_final:
            response = await conversation_agent.ask(transcription.text)
            await websocket.send_json({
                "type": "response",
                "text": response
            })
```

### Frontend (Web UI)

```javascript
// Browser microphone → WebSocket

const ws = new WebSocket('ws://localhost:8000/ws/voice');

// Start microphone
navigator.mediaDevices.getUserMedia({ audio: true })
  .then(stream => {
    const audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (e) => {
      const audioData = e.inputBuffer.getChannelData(0);
      const int16Data = float32ToInt16(audioData);
      const base64 = btoa(String.fromCharCode(...int16Data));

      // Send to server
      ws.send(JSON.stringify({
        type: 'audio_chunk',
        data: base64,
        sequence: sequenceNumber++
      }));
    };

    source.connect(processor);
    processor.connect(audioContext.destination);
  });

// Receive transcriptions
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'transcription') {
    // Display transcription (real-time)
    document.getElementById('transcription').textContent = message.text;

    if (message.is_final) {
      // Add to history
      addToHistory(message.text);
    }
  }

  if (message.type === 'response') {
    // Display AI response
    document.getElementById('response').textContent = message.text;

    // Optional: Convert to speech (TTS)
    speakText(message.text);
  }
};
```

## 📝 Complete Implementation Checklist

### Phase 1: Core Service (Estimated: 4-6 hours)
- [ ] WebSocket handler implementation
- [ ] Session management
- [ ] Audio stream processing integration
- [ ] STT streaming coordination
- [ ] Error handling & reconnection logic

### Phase 2: Conversation Integration (Estimated: 2-3 hours)
- [ ] Conversation agent client
- [ ] Request/response handling
- [ ] Context management
- [ ] Session persistence

### Phase 3: Web UI (Estimated: 3-4 hours)
- [ ] Microphone capture
- [ ] Audio processing (resampling to 16kHz)
- [ ] WebSocket client
- [ ] Real-time transcription display
- [ ] Conversation history
- [ ] Audio visualization (optional)

### Phase 4: Testing & Polish (Estimated: 2-3 hours)
- [ ] End-to-end testing
- [ ] Latency optimization
- [ ] Error scenario testing
- [ ] Documentation
- [ ] Example usage

**Total Estimated Time: 11-16 hours of focused development**

## 🚀 Quick Start (Mevcut Sistem ile Test)

Şu anda streaming STT altyapısı hazır. Test etmek için:

### 1. STT Streaming Test

```python
import asyncio
from shared.speech_to_text import get_stt_provider

async def test_streaming():
    stt = get_stt_provider()

    # Simulate audio stream
    async def audio_stream():
        with open("test_audio.wav", "rb") as f:
            while chunk := f.read(4096):
                yield chunk
                await asyncio.sleep(0.01)  # Simulate real-time

    # Stream transcription
    async for result in stt.transcribe_stream(
        audio_stream=audio_stream(),
        language="tr"
    ):
        print(f"[{'FINAL' if result.is_final else 'INTERIM'}] {result.text}")

asyncio.run(test_streaming())
```

## 🎯 Sonraki Adımlar

**Option A: Full Implementation** (Ben implement edeyim, 4-6 saat)
- Complete WebSocket handler
- Complete Voice Service
- Complete Web UI
- End-to-end working system

**Option B: Gradual Implementation** (Step by step)
1. First: WebSocket handler only (2 hours)
2. Then: Basic web UI (2 hours)
3. Then: Full integration (2 hours)

**Option C: Guided Implementation** (Siz implement edin, ben guide edeyim)
- I provide detailed code for each component
- You integrate piece by piece
- I help debug issues

**Hangi yolu tercih edersiniz?**

## 📊 Current Status Summary

✅ **Infrastructure: 90% Complete**
- STT providers ready
- Streaming architecture ready
- Security & validation ready
- Metrics & logging ready

⚠️ **Service Layer: 30% Complete**
- Config ready
- Schemas ready
- WebSocket handler missing
- Voice service logic missing

❌ **Frontend: 0% Complete**
- No web UI yet
- No microphone integration
- No WebSocket client

## 💡 Önerilen Approach

**Ben devam edeyim mi?**

Şu anda:
1. ✅ STT altyapısı %100 hazır (batch + streaming)
2. ✅ Audio processing infrastructure hazır
3. ⚠️ Voice Service %30 hazır
4. ❌ Web UI yok

**Devam edersem:**
- 2-3 saat: WebSocket handler + Voice Service
- 1-2 saat: Basic Web UI
- 1 saat: Integration & testing
- **Toplam: ~5 saat** → Fully working real-time voice assistant

**Ne dersiniz?** Devam edeyim mi yoksa bu altyapı yeterli mi?
