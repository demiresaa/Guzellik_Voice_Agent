# Güzellik Merkezi Randevu Asistanı - Enterprise Architecture

## Sistem Genel Bakış

Mikroservis mimarisi ile kurulmuş, büyük ölçekli (1000+ eşzamanlı kullanıcı) destekleyen,
güvenli ve ölçeklenebilir bir AI randevu asistanı sistemi.

## Mimari Prensipler

### 1. Separation of Concerns
- Her servis tek bir sorumluluk alanına sahip
- Loose coupling, high cohesion
- Domain-Driven Design (DDD)

### 2. Security First
- Zero Trust Architecture
- Defense in Depth (çok katmanlı güvenlik)
- OWASP Top 10 koruması
- GDPR/KVKK compliance

### 3. Scalability & Performance
- Horizontal scaling (Kubernetes)
- Stateless services
- Redis caching
- Connection pooling
- Rate limiting

### 4. Observability
- Structured logging (JSON)
- Distributed tracing (OpenTelemetry)
- Metrics (Prometheus)
- Health checks

### 5. Resilience
- Circuit breakers
- Retry with exponential backoff
- Graceful degradation
- Database connection pooling

## Servis Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│                     API Gateway (Kong)                      │
│  - Authentication (JWT)                                     │
│  - Rate Limiting (IP + User)                                │
│  - Request Routing                                          │
│  - TLS Termination                                          │
└───────────────────┬─────────────────────────────────────────┘
                    │
        ┌───────────┼───────────────┐
        │           │               │
┌───────▼───────┐ ┌─▼──────────┐ ┌─▼─────────────┐
│Voice Interface│ │Conversation│ │Booking Agent  │
│Client Service │ │Agent Service│ │Service        │
│               │ │            │ │               │
│Port: 8000     │ │Port: 8002  │ │Port: 8001     │
│               │ │            │ │               │
│- Audio I/O    │ │- LangChain │ │- 9 Tools      │
│- STT (Whisper)│ │- Gemini LLM│ │- Business     │
│- SSE Client   │ │- SSE Stream│ │  Logic        │
│- WebUI        │ │- Session   │ │- Repository   │
└───────────────┘ └─────┬──────┘ └───────┬───────┘
                        │                │
                        │                │
        ┌───────────────┼────────────────┤
        │               │                │
┌───────▼───┐   ┌───────▼────┐   ┌──────▼──────┐
│  Redis    │   │PostgreSQL  │   │   S3/Blob   │
│           │   │            │   │             │
│- Sessions │   │- Users     │   │- Audio Logs │
│- Cache    │   │- History   │   │- Backups    │
│- RateLim  │   │- Analytics │   │             │
└───────────┘   └────────────┘   └─────────────┘
```

## Servis Detayları

### 1. Voice Interface Client Service (Port 8000)
**Sorumluluk:** Kullanıcı arayüzü ve ses işleme

**Teknolojiler:**
- FastAPI (REST + WebSocket)
- faster-whisper (STT)
- sounddevice (Audio capture)
- SSE EventSource

**Endpoints:**
- `GET /` - Web UI
- `POST /api/transcribe` - Audio → Text
- `WS /ws/voice` - Real-time voice streaming
- `GET /health` - Health check

**Scaling:** Edge deployment (closest to users)

---

### 2. Conversation Agent Service (Port 8002)
**Sorumluluk:** LLM orchestration ve conversation management

**Teknolojiler:**
- FastAPI
- LangChain (Agent framework)
- Google Gemini 2.0 Flash
- Redis (session storage)
- PostgreSQL (conversation history)

**Endpoints:**
- `POST /api/conversation/stream` - SSE streaming response
- `POST /api/conversation/sync` - Synchronous response
- `GET /api/conversation/history` - Get conversation history
- `DELETE /api/conversation/session` - Clear session
- `GET /health` - Health check

**Features:**
- Token-by-token streaming (SSE)
- Session management (Redis)
- Conversation history (PostgreSQL)
- Tool calling orchestration
- Context window management

**Scaling:** CPU-intensive, auto-scale 5-50 replicas

---

### 3. Booking Agent Service (Port 8001)
**Sorumluluk:** Business logic ve data management

**Teknolojiler:**
- FastAPI
- PostgreSQL (primary database)
- Redis (caching)

**Existing 9 Tools:**
1. getCustomerInfoByPhone
2. createOrUpdateCustomer
3. checkAvailability
4. createAppointment
5. cancelAppointment
6. getComplementaryServiceSuggestions
7. getActiveCampaignsForCustomer
8. sendSmsNotification
9. requestPrepayment

**Scaling:** Database-heavy, auto-scale 3-20 replicas

---

## Data Flow

### Conversation Request Flow
```
User speaks → Voice Client captures audio
            → STT (faster-whisper) → Text
            → POST /api/conversation/stream (text)
            → Conversation Agent (LLM decides tools)
            → Call Booking Agent tools (HTTP REST)
            → LLM generates response
            → SSE stream → Voice Client
            → Display to user
```

### Session Management
```
User connects → JWT issued (API Gateway)
              → Session created (Redis, 30min TTL)
              → Conversation history stored (PostgreSQL)
              → Session cleanup on disconnect
```

## Security Architecture

### Layer 1: Network (Perimeter)
- CloudFlare DDoS protection
- WAF (Web Application Firewall)
- TLS 1.3 only

### Layer 2: API Gateway
- JWT authentication (RS256)
- API key validation (constant-time comparison)
- Rate limiting:
  - Global: 1000 req/min
  - Per IP: 100 req/min
  - Per user: 50 req/min

### Layer 3: Service Level
```python
# Each service has:
@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000"
    return response
```

### Layer 4: Application
- Input validation (Pydantic)
- SQL injection prevention (ORM)
- XSS protection (output escaping)
- CSRF tokens
- Request signing (HMAC)

### Layer 5: Data
- Encryption at rest (AES-256)
- Encryption in transit (TLS 1.3)
- PII masking in logs
- Audit logging

## Observability

### Logging
```python
# Structured JSON logging
{
  "timestamp": "2025-10-29T12:34:56Z",
  "service": "conversation-agent",
  "level": "INFO",
  "trace_id": "abc123",
  "user_id": "user-456",
  "action": "tool_call",
  "tool": "create_appointment",
  "duration_ms": 234,
  "success": true
}
```

### Metrics (Prometheus)
- Request rate, latency, error rate
- Tool call success/failure
- LLM token usage
- Database query times
- Cache hit rate

### Tracing (Jaeger)
- End-to-end request tracing
- Tool call attribution
- Performance bottleneck identification

### Health Checks
```python
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "checks": {
            "database": check_db_connection(),
            "redis": check_redis_connection(),
            "llm": check_llm_availability()
        }
    }
```

## Deployment

### Docker Compose (Development)
```bash
docker-compose up -d
# Services start on localhost:8000, :8001, :8002
```

### Kubernetes (Production)
```bash
kubectl apply -f infrastructure/kubernetes/
# Auto-scaling, load balancing, health checks
```

### Environment Variables
```bash
# Required for each service
ENVIRONMENT=production
LOG_LEVEL=INFO
DATABASE_URL=postgresql://...
REDIS_URL=redis://...
GEMINI_API_KEY=...
JWT_SECRET=...
```

## Performance Targets

| Metric | Target | Max |
|--------|--------|-----|
| Response Time (P95) | < 2s | < 5s |
| Throughput | 1000 req/s | 5000 req/s |
| Availability | 99.9% | - |
| Error Rate | < 0.1% | < 1% |
| Concurrent Users | 1000+ | 10000+ |

## Disaster Recovery

- **Backup:** Daily PostgreSQL backups (retained 30 days)
- **Replication:** Multi-region database replication
- **Failover:** Automatic failover (< 30s downtime)
- **Recovery Time Objective (RTO):** < 1 hour
- **Recovery Point Objective (RPO):** < 15 minutes

---

**Version:** 2.0.0
**Last Updated:** 2025-10-29
**Author:** Staff Engineering Team
