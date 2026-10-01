# Akıllı Servis Masası Chatbot

#ER DİYAGRAMI
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