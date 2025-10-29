# Güzellik Merkezi Randevu Asistanı - Enterprise Architecture

🏢 **Enterprise-grade distributed microservices architecture** for AI-powered beauty salon booking assistant.

**Version:** 2.0.0
**Architecture:** Microservices + SSE Streaming
**Target Scale:** 1000+ concurrent users

---

## 📋 Table of Contents

- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Services](#services)
- [Development](#development)
- [Deployment](#deployment)
- [Security](#security)

---

## 🎯 System Overview

Enterprise AI randevu sistemi, 3 mikroservis ile dağıtık mimari kullanarak:

### Core Services

| Service | Port | Description |
|---------|------|-------------|
| **Conversation Agent** | 8002 | LangChain orchestration + SSE streaming |
| **Booking Agent** | 8001 | Business logic + 9 specialized tools |
| **Voice Interface** | 8000 | Audio I/O + STT client |

### Infrastructure

- **PostgreSQL**: Conversation history + booking data
- **Redis**: Session management + rate limiting + caching
- **API Gateway** (optional): Kong/Traefik for production

---

## 🏗️ Architecture

```
Internet
   │
   ▼
[Load Balancer]
   │
   ▼
[API Gateway] ← JWT Auth, Rate Limiting
   │
   ├─────────────────┬──────────────────┐
   ▼                 ▼                  ▼
[Voice Interface]  [Conversation Agent] [Booking Agent]
Port: 8000         Port: 8002           Port: 8001
   │                 │                   │
   │                 ├──────────────────►│ (HTTP REST)
   │                 │                   │
   └─────────────────┤                   │
                     ▼                   ▼
                 [PostgreSQL]        [PostgreSQL]
                     │
                     ▼
                  [Redis]
```

**Data Flow:**
```
User speaks → STT (local) → Text
            → POST /api/conversation/stream
            → LangChain Agent (tool calling)
            → Booking Agent API (9 tools)
            → SSE Stream (token by token)
            → User sees response
```

---

## ✨ Features

### 🔐 Security First
- **Multi-layer security**: API Gateway → Service → Application → Data
- **Authentication**: JWT + API Key (constant-time comparison)
- **Rate Limiting**: Token bucket algorithm (Redis distributed)
- **Input Validation**: XSS, SQL injection, NoSQL injection protection
- **Encryption**: AES-256 at rest, TLS 1.3 in transit
- **GDPR/KVKK**: PII masking in logs, consent tracking

### 🚀 Scalability
- **Horizontal scaling**: Kubernetes auto-scaling (5-50 replicas)
- **Stateless services**: Redis for session state
- **Connection pooling**: PostgreSQL (10 pool size, 20 overflow)
- **Caching**: Redis (30-min TTL)
- **Load balancing**: AWS ELB / Nginx

### 📊 Observability
- **Structured Logging**: JSON format (ELK compatible)
- **Distributed Tracing**: OpenTelemetry + Jaeger
- **Metrics**: Prometheus + Grafana
- **Health Checks**: `/health`, `/ready`, `/live` endpoints

### 🤖 AI Features
- **LangChain Integration**: Tool-calling agent orchestration
- **SSE Streaming**: Token-by-token response (real-time UX)
- **Context Management**: Last 20 messages in context window
- **Tool Calling**: 7 tools (customer, booking, marketing)
- **Session Management**: 30-min TTL, Redis-backed

---

## 🚀 Quick Start

### Prerequisites

```bash
# Required
- Python 3.11+
- PostgreSQL 14+
- Redis 7+

# Optional (for production)
- Docker & Docker Compose
- Kubernetes cluster
```

### 1. Clone Repository

```bash
git clone <repository-url>
cd Guzellik_Voice_Agent
```

### 2. Install Dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### 3. Setup Environment

```bash
# Copy example config
cp .env.example .env

# Generate secure keys
python -c "import secrets; print(secrets.token_hex(32))"

# Edit .env with your keys
nano .env
```

**Minimum required:**
```bash
GEMINI_API_KEY=your_actual_gemini_api_key
API_KEY=<generated_64_char_key>
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/guzellik_booking
REDIS_URL=redis://localhost:6379/0
```

### 4. Setup Database

```bash
# Start PostgreSQL (Docker)
docker run -d \
  --name postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=guzellik_booking \
  -p 5432:5432 \
  postgres:14

# Start Redis (Docker)
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:7-alpine
```

### 5. Run Services

**Terminal 1 - Booking Agent:**
```bash
cd services/booking_agent_service
python main.py
# Runs on http://localhost:8001
```

**Terminal 2 - Conversation Agent:**
```bash
cd services/conversation_agent_service
python main.py
# Runs on http://localhost:8002
```

**Terminal 3 - Voice Interface (coming soon):**
```bash
# Voice Interface will be implemented as SSE client
# Currently in development
```

### 6. Test API

```bash
# Create session
curl -X POST http://localhost:8002/api/conversation/session \
  -H "X-API-Key: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "05321234567"}'

# SSE Stream conversation
curl -N -X POST http://localhost:8002/api/conversation/stream \
  -H "X-API-Key: <your_api_key>" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "sess_xxx",
    "message": "Yarın saat 14:00 için randevu almak istiyorum",
    "phone_number": "05321234567"
  }'
```

---

## 📦 Services

### Conversation Agent Service (Port 8002)

**Endpoints:**
- `POST /api/conversation/stream` - SSE streaming conversation
- `GET /api/conversation/history/{session_id}` - Get conversation history
- `POST /api/conversation/session` - Create session
- `DELETE /api/conversation/session/{session_id}` - End session
- `GET /health` - Health check

**Features:**
- LangChain agent with 7 tools
- SSE streaming (token-by-token)
- Redis session management (30-min TTL)
- PostgreSQL conversation history
- Full observability

### Booking Agent Service (Port 8001)

**9 Tools:**
1. `getCustomerInfoByPhone` - Customer lookup
2. `createOrUpdateCustomer` - Customer management
3. `checkAvailability` - Find available slots
4. `createAppointment` - Book appointment
5. `cancelAppointment` - Cancel booking
6. `getComplementaryServiceSuggestions` - Upselling
7. `getActiveCampaignsForCustomer` - Personalized campaigns
8. `sendSmsNotification` - SMS notifications
9. `requestPrepayment` - Payment links

---

## 🛠️ Development

### Project Structure

```
Guzellik_Voice_Agent/
├── shared/                        # Shared libraries (12 modules)
│   ├── common/                    # Config, logging, exceptions, models
│   ├── security/                  # Auth, rate limiting, encryption, validation
│   └── database/                  # Async SQLAlchemy + repository pattern
│
├── services/                      # Microservices
│   ├── conversation_agent_service/ (Port 8002) ✅ NEW
│   │   ├── app/
│   │   │   ├── api/routes/        # FastAPI routes
│   │   │   ├── models/            # SQLAlchemy models (Conversation, Message)
│   │   │   ├── schemas/           # Pydantic request/response schemas
│   │   │   ├── repositories/      # Data access layer
│   │   │   └── services/          # Business logic (LangChain + SSE)
│   │   ├── config.py              # Service-specific config
│   │   ├── dependencies.py        # DI container
│   │   └── main.py                # FastAPI app with lifespan
│   │
│   ├── booking_agent_service/     (Port 8001) ✅ MIGRATED
│   │   ├── api/routes/            # 9 tool endpoints
│   │   ├── models/                # Domain models
│   │   ├── repositories/          # In-memory database
│   │   ├── services/              # Business logic
│   │   ├── security/              # Auth & rate limiting
│   │   ├── config.py
│   │   └── main.py
│   │
│   └── voice_interface_client/    (Port 8000) 🚧 PLANNED
│       # Will be implemented as SSE client
│
├── infrastructure/                # DevOps
│   ├── docker/                    # Docker Compose
│   ├── kubernetes/                # K8s manifests
│   └── monitoring/                # Prometheus + Grafana
│
├── ARCHITECTURE.md                # Detailed system architecture (302 lines)
├── README.md                      # This file
├── requirements.txt               # Python dependencies (50 packages)
└── .env.example                   # Environment template (116 lines)
```

### Running Tests

```bash
# Unit tests
pytest tests/unit -v

# Integration tests
pytest tests/integration -v

# Coverage
pytest --cov=services --cov-report=html
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy services/

# Format
black services/
```

---

## 🚢 Deployment

### Docker Compose (Development)

```bash
docker-compose up -d
```

### Kubernetes (Production)

```bash
# Apply manifests
kubectl apply -f infrastructure/kubernetes/

# Check status
kubectl get pods -n guzellik-booking

# Scale conversation agent
kubectl scale deployment conversation-agent --replicas=10
```

### Environment Variables (Production)

```bash
ENVIRONMENT=production
LOG_FORMAT=json
DATABASE_URL=postgresql+asyncpg://user:pass@db-host:5432/dbname
REDIS_URL=rediss://user:pass@redis-host:6379/0
ENABLE_METRICS=True
ENABLE_TRACING=True
```

---

## 🔒 Security

### Best Practices Implemented

1. **Zero Trust Architecture**: Every request validated
2. **Defense in Depth**: Multiple security layers
3. **Least Privilege**: Minimal permissions
4. **Secure by Default**: Safe defaults in config
5. **Input Validation**: All inputs sanitized
6. **Output Encoding**: Prevent XSS
7. **Secrets Management**: Never commit secrets
8. **Audit Logging**: All actions logged
9. **Rate Limiting**: DDoS protection
10. **Encryption**: At rest and in transit

### Security Checklist

- [ ] Change default API_KEY in .env
- [ ] Generate strong JWT_SECRET (32+ chars)
- [ ] Enable TLS/HTTPS in production
- [ ] Configure firewall rules
- [ ] Setup Redis password
- [ ] Enable PostgreSQL SSL
- [ ] Review CORS allowed origins
- [ ] Enable rate limiting
- [ ] Setup monitoring alerts
- [ ] Regular security audits

---

## 📊 Performance Targets

| Metric | Target | Max |
|--------|--------|-----|
| Response Time (P95) | < 2s | < 5s |
| Throughput | 1000 req/s | 5000 req/s |
| Availability | 99.9% | - |
| Error Rate | < 0.1% | < 1% |
| Concurrent Users | 1000+ | 10000+ |

---

## 📚 Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Detailed system architecture
- [API Docs](http://localhost:8002/docs) - Swagger UI (development)
- [Health Dashboard](http://localhost:8002/health) - Service health

---

## 🤝 Contributing

Bu bir enterprise production sistemidir. Değişiklikler için:

1. Feature branch oluştur
2. Tests yaz
3. Code review bekle
4. Main'e merge

---

## 📝 License

Proprietary - © 2025 Güzellik Merkezi

---

## 🙋 Support

**Staff Engineering Team**

- Architecture Questions: Check ARCHITECTURE.md
- Technical Issues: GitHub Issues
- Security Concerns: security@company.com

---

**Built with ❤️ by Staff Engineers**
