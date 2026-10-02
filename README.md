# Akıllı Servis Masası Chatbot

# ER DİYAGRAMI

```mermaid
erDiagram
    USERS ||--o{ CHAT_SESSIONS : "owns"
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : "contains"
    CHAT_MESSAGES ||--o| FEEDBACKS : "receives"
    CHAT_MESSAGES }o--o{ KNOWLEDGE_BASE_TICKETS : "references"

    USERS {
        uuid id PK
        string email UK
        string password_hash
        string role
        timestamp created_at
    }

    CHAT_SESSIONS {
        uuid id PK
        uuid user_id FK
        string title
        string expert_mode
        timestamp created_at
    }

    CHAT_MESSAGES {
        uuid id PK
        uuid session_id FK
        string sender
        text message_text
        json retrieved_context_ids
        timestamp created_at
    }

    FEEDBACKS {
        uuid id PK
        uuid message_id FK
        int rating
        text comment
        timestamp created_at
    }

    KNOWLEDGE_BASE_TICKETS {
        uuid id PK
        string ticket_code
        string category
        text issue_description
        text resolution
        vector embedding
        timestamp created_at
    }
```
```mermaid
flowchart TB
    %% 1. ve 2. Süreç: Yan Yana Üst Bloklar
    subgraph S1 ["1. Veri Hazırlama & İndeksleme (Batch Süreci)"]
        A[Kaggle / UCI Servis Masası Bilet Verisi] --> B[Veri Temizleme & Ön İşleme]
        B --> C[Metin Parçalama / Chunking]
        C --> D[OpenAI text-embedding-3-small]
        D -->|Vektör + Metin| E[(PostgreSQL / pgvector)]
    end

    subgraph S2 ["2. Kullanıcı Sorgusu & Vektör Arama (Online Süreç)"]
        U[Kullanıcı Sorusu] --> F[OpenAI Embedding Modeli]
        F -->|Soru Vektörü| G{Kosinüs Benzerlik Araması}
        G -->|En Benzer 3-5 Bilet Kaydı| H[Bağlam / Context]
    end

    %% S1 ve S2'nin yan yana durmasını sağlayan görünmez yatay bağ
    S1 ~~~ S2

    %% 1 ve 2 arasındaki dinamik veri köprüsü
    E -.->|Vektör Karşılaştırması| G

    %% 3. Süreç: Alt Katman (Yanıt Üretimi)
    subgraph S3 ["3. LLM Yanıt Üretimi & Sunum"]
        SP[Sistem Promptu: Windows/Oracle Uzmanı] --> I[Prompt Birleştirici]
        CH[Geçmiş Sohbet Hafızası / History] --> I
        I -->|Zenginleştirilmiş İstek| J[LLM: OpenAI GPT-4o-mini]
        J --> K[Markdown / Kod Bloklu Yanıt]
        K --> L[Kullanıcı Arayüzü / Chat Dashboard]
    end

    %% Üst Süreçlerden Alt Süreçteki Prompt Birleştiriciye Giden Orijinal Bağlantılar
    H --> I
    U --> I

    %% Görsel Stiller
    classDef db fill:#e1f5fe,stroke:#0288d1,stroke-width:2px;
    classDef llm fill:#ede7f6,stroke:#512da8,stroke-width:2px;

    class E db;
    class D,F,J llm;
```

```mermaid
flowchart TB
  subgraph HAZIRLIK["1. Veri hazırlama (bir kez ve Bilgi Merkezi yüklemesinde)"]
    K1["Kaggle ticket verisi (CSV)"]
    K2["Stack Exchange alt kümesi"]
    K3["Admin: Bilgi Merkezi dosya yükleme"]
    T["Temizle: HTML, yer tutucu, tekrar"]
    CH["Chunk'la"]
    EM["Embedding: multilingual-e5-base (passage: öneki)"]
    K1 --> T
    K2 --> T
    K3 --> T
    T --> CH --> EM
  end

  subgraph PGS["PostgreSQL (vektör deposu)"]
    PG[("document_chunks: metin + embedding")]
  end

  subgraph MSS["MSSQL (kullanıcı yönetimi ve loglama)"]
    USERS[("Users")]
    KD[("KnowledgeDocuments")]
    SESS[("ChatSessions, Messages, MessageSources")]
    FB[("Feedbacks")]
    AUD[("AuditLogs")]
  end

  subgraph SORU["2. Soru-cevap (her soruda)"]
    U["Kullanıcı: Streamlit chat"]
    API["FastAPI: JWT doğrulama"]
    MODE["Uzman modu: Genel, Windows Server, Oracle DB"]
    QE["Soru embedding: e5 (query: öneki)"]
    SR["Benzerlik araması: top-k"]
    PR["Prompt: sistem prompt + bağlam + sohbet geçmişi + soru"]
    LLM["LLM: OpenAI küçük model"]
    ANS["Cevap: Markdown, kod bloğu, kaynak bağlantısı"]
    SHOW["Ekranda gösterilir"]
    U --> API --> MODE --> QE --> SR --> PR --> LLM --> ANS --> SHOW
  end

  subgraph YONETIM["3. Geri bildirim ve yönetim"]
    PUAN["Kullanıcı cevabı puanlar"]
    ADM["Admin paneli: en çok sorulanlar, başarı oranı"]
  end

  EM -->|"vektör + metin"| PG
  K3 -->|"dosya kaydı (document_id)"| KD
  KD -.->|"aynı document_id ile senkron"| PG
  PG -->|"benzer parçalar"| SR
  API <-->|"kullanıcı ve rol"| USERS
  API -.->|"giriş ve hata kaydı"| AUD
  SESS -->|"son mesajlar"| PR
  ANS -->|"mesaj + kullanılan parçalar"| SESS
  SHOW --> PUAN
  PUAN -->|"puan"| FB
  FB --> ADM
  SESS --> ADM

  classDef proc fill:#EEEDFE,stroke:#534AB7,color:#26215C
  classDef db fill:#E1F5EE,stroke:#0F6E56,color:#04342C
  class K1,K2,K3,T,CH,EM,U,API,MODE,QE,SR,PR,LLM,ANS,SHOW,PUAN,ADM proc
  class PG,USERS,KD,SESS,FB,AUD db

  ```