# 🎤 AI Sesli Asistan - Güzellik Merkezi Randevu Sistemi

Bu proje, güzellik merkezi gibi işletmeler için tasarlanmış, gerçek zamanlı, ses tabanlı bir yapay zeka randevu asistanıdır. Müşteriler, doğal bir konuşma diliyle randevu alabilir, müsaitlik durumu sorgulayabilir ve kampanyalar hakkında bilgi alabilirler.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg)](https://fastapi.tiangolo.com/)
[![LangChain](https://img.shields.io/badge/LangChain-0.1-orange.svg)](https://www.langchain.com/)
[![WebSocket](https://img.shields.io/badge/WebSocket-✓-green.svg)](#)

---

## 🌟 Temel Özellikler

- **🗣️ Gerçek Zamanlı Ses Tanıma:** Kullanıcının konuşması, `Faster-Whisper` modeli kullanılarak anlık olarak metne çevrilir.
- **🧠 Akıllı Diyalog Yönetimi:** `Google Gemini` ve `LangChain` ajanları, kullanıcının niyetini anlar ve gerekli adımları belirler.
- **🛠️ Araç Kullanımı (Tool Calling):** Yapay zeka, randevu oluşturma, müsaitlik kontrolü gibi işlemler için arka plan servislerinin sunduğu araçları otonom olarak kullanır.
- **🔊 Sesli Yanıt (Text-to-Speech):** Asistanın ürettiği metin cevapları, tarayıcının kendi ses motoru kullanılarak kullanıcıya sesli olarak okunur.
- ** scalable Mikroservis Mimarisi:** Sistem, her biri kendi sorumluluğuna sahip üç ana servisten oluşur, bu da esneklik ve ölçeklenebilirlik sağlar.
- **🌐 Web Tabanlı Arayüz:** Kullanıcıların sistemi kolayca kullanabilmesi için basit ve modern bir web arayüzü sunar.

---

## 🏗️ Mimari

Sistem, birbiriyle REST API ve WebSocket üzerinden haberleşen üç ana mikroservisten oluşur:

```
┌─────────────────────────────────────────────────────────────┐
│                    KULLANICI (Browser)                      │
│          Mikrofon + Web Arayüzü + Sesli Yanıt (TTS)         │
└───────────────────────────┬─────────────────────────────────┘
                            │ WebSocket (Port 8000)
                            │ Audio Stream (16kHz, mono)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              VOICE INTERFACE SERVICE (Port 8000)            │
│ ┌─────────────┐ ┌─────────────┐ ┌───────────────────────┐ │
│ │ WebSocket   │ │ Oturum      │ │ Ses Akışı & Çevirme   │ │
│ │ Yönetimi    │ │ Yönetimi    │ │ (STT)                 │ │
│ └─────────────┘ └─────────────┘ └───────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │ Metin (JSON/HTTP)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│         CONVERSATION AGENT SERVICE (Port 8002)              │
│ ┌──────────────────────────────────────────────────────┐ │
│ │           Gemini LLM + LangChain Agent               │ │
│ │  - Niyet anlama                                      │ │
│ │  - Diyalog yönetimi                                  │ │
│ │  - Araç çağırma (Tool Calling)                       │ │
│ └──────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │ Araç Çağrısı (JSON/HTTP)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│          BOOKING AGENT SERVICE (Port 8001)                  │
│ ┌──────────────────────────────────────────────────────┐ │
│ │                 İş Mantığı ve Araçlar                │ │
│ │  - Müsaitlik kontrolü                                │ │
│ │  - Randevu oluşturma/iptal etme                      │ │
│ │  - Müşteri bilgisi sorgulama                         │ │
│ └──────────────────────────────────────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
                  ┌─────────────────┐
                  │   Veritabanı    │
                  │  (PostgreSQL)   │
                  └─────────────────┘
```

---

## 🛠️ Teknoloji Stack'i

- **Backend:** FastAPI, Uvicorn, LangChain, Pydantic
- **Ses Tanıma (STT):** Faster-Whisper
- **Yapay Zeka (LLM):** Google Gemini
- **Veritabanı:** PostgreSQL (simüle edilmiş)
- **İletişim:** WebSocket, HTTP, REST
- **Frontend:** Vanilla JavaScript, HTML5, CSS3, Web Speech API (TTS)
- **Asenkron Programlama:** asyncio, aiohttp

---

## 🚀 Kurulum ve Başlatma

### Gereksinimler
- Python 3.10+
- `pip` paket yöneticisi

### Kurulum Adımları

1.  **Projeyi Klonlayın:**
    ```bash
    git clone <repository_url>
    cd Guzellik_Voice_Agent
    ```

2.  **Sanal Ortam Oluşturun ve Aktif Edin:**
    ```bash
    # Windows
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1

    # macOS / Linux
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Bağımlılıkları Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Yapılandırma Dosyasını Oluşturun:**
    *   Projenin ana dizinindeki `.env.example` dosyasını kopyalayarak `.env` adında yeni bir dosya oluşturun.
    *   **.env dosyasını açın ve özellikle `GEMINI_API_KEY` değişkenini kendi geçerli Google AI API anahtarınızla güncelleyin.** Yapay zekanın çalışması için bu adım zorunludur.

### Nihai Başlatma Prosedürü

Sistemin çalışması için **üç servisin de aynı anda, üç ayrı terminalde** çalışıyor olması gerekir.

1.  **TERMINAL 1'i Açın (Booking Servisi):**
    *   Bu terminalde aşağıdaki komutu çalıştırın ve arka planda çalışır durumda bırakın:
        ```bash
        python -m services.booking_agent_service.main
        ```

2.  **TERMINAL 2'yi Açın (Yapay Zeka Servisi):**
    *   Bu yeni terminalde aşağıdaki komutu çalıştırın ve arka planda çalışır durumda bırakın:
        ```bash
        python -m services.conversation_agent_service.main
        ```

3.  **TERMINAL 3'ü Açın (Ses Arayüzü Servisi):**
    *   Bu üçüncü terminalde aşağıdaki komutu çalıştırın ve arka planda çalışır durumda bırakın:
        ```bash
        python -m services.voice_interface_service.main
        ```
    *   **Not:** Bu servisi ilk kez başlattığınızda, `faster-whisper` modeli internetten indirilecektir. Bu işlem birkaç dakika sürebilir, lütfen sabırla bekleyin.

---

## 💻 Nasıl Kullanılır?

1.  Yukarıdaki üç servis de çalışır durumdayken, bir web tarayıcısı açın.
2.  `http://localhost:8000` adresine gidin.
3.  Tarayıcınız mikrofon erişimi için izin istediğinde **"İzin Ver"** seçeneğine tıklayın.
4.  Ortadaki büyük mikrofon butonuna basın ve konuşmaya başlayın.
5.  Konuşmanız ekranda metne çevrilecek ve kısa bir süre sonra asistanın cevabı hem ekranda görünecek hem de size sesli olarak okunacaktır.

---

## 📂 Proje Yapısı

- **`/services/`**: Üç ana mikroservisin kodlarını içerir.
  - `booking_agent_service/`: Randevu ve müşteri yönetimi gibi iş mantığını barındırır.
  - `conversation_agent_service/`: Yapay zeka, diyalog yönetimi ve araç çağırma mantığını içerir.
  - `voice_interface_service/`: WebSocket bağlantılarını, ses akışını ve web arayüzünü yönetir.
- **`/shared/`**: Tüm servisler tarafından paylaşılan ortak kodları (veritabanı erişimi, güvenlik, STT altyapısı vb.) içerir.
- **`requirements.txt`**: Projenin Python bağımlılıklarını listeler.
- **`.env`**: Servislerin yapılandırma ve API anahtarı gibi gizli bilgilerini içerir. (Bu dosya repoya dahil edilmemelidir).