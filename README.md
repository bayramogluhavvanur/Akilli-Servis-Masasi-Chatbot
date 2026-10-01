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