# Akıllı Servis Masası Chatbot

**ER DİYAGRAMI**
```mermaid
erDiagram

  USERS{
   int user_id PK
   string email UK
   string password_hash 
   string role
   timestap created_at
   }

  CHAT_SESSIONS {
   int chat_s_id PK
   int user_id FK
   string title 
   string expert_mode
   timestap created_at
   }

  CHAT_MESSAGES{
   int chat_m_id PK
   int chat_s_id FK
   string sender
   text message_text
   json retrieved_context_ids
   timestap created_at
   }

  FEEDBACKS {
   int feedbakcs_id PK
   int chat_m_id FK
   int rating 
   text comment
   timestap created_at
   }
  KNOWLEDGE_BASE_TICEKTS{
   int knowledge_id PK
   string ticket_code
   string category
   text issue_description
   text resolution
   vector embedding 
   timestap created_at
   }    

   USERS ||--o{ CHAT_SESSIONS : "owns"
    CHAT_SESSIONS ||--o{ CHAT_MESSAGES : "contains"
    CHAT_MESSAGES ||--o| FEEDBACKS : "receives"
    CHAT_MESSAGES }o--o{ KNOWLEDGE_BASE_TICKETS : "references"

``` 