CREATE DATABASE ServisMasasi_Auth;
GO

USE ServisMasasi_Auth;
GO

-- 1. Users Tablosu
CREATE TABLE Users (
    user_id INT IDENTITY(1,1) PRIMARY KEY,
    username NVARCHAR(50) NOT NULL UNIQUE,
    password_hash NVARCHAR(255) NOT NULL,
    full_name NVARCHAR(100) NOT NULL,
    role NVARCHAR(20) DEFAULT 'user',
    created_at DATETIME2 DEFAULT GETDATE()
);
GO

-- 2. ChatSessions Tablosu
CREATE TABLE ChatSessions (
    session_id INT IDENTITY(1,1) PRIMARY KEY,
    user_id INT NOT NULL,	
    session_title NVARCHAR(200) DEFAULT 'Yeni Destek Talebi',
    started_at DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT FK_Sessions_Users FOREIGN KEY (user_id) REFERENCES Users(user_id) ON DELETE CASCADE
);
GO

-- 3. ChatMessages Tablosu
CREATE TABLE ChatMessages (
    message_id INT IDENTITY(1,1) PRIMARY KEY,
    session_id INT NOT NULL,
    sender NVARCHAR(20) NOT NULL,
    message_text NVARCHAR(MAX) NOT NULL,
    retrieved_sources NVARCHAR(MAX) NULL,
    similarity_score FLOAT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT FK_Messages_Sessions FOREIGN KEY (session_id) REFERENCES ChatSessions(session_id) ON DELETE CASCADE
);
GO

-- ==========================================
-- SİSTEM METRİKLERİ VE LOGLARI İÇİN TABLO
-- ==========================================
CREATE TABLE ChatLogs (
    log_id INT IDENTITY(1,1) PRIMARY KEY,
    session_id NVARCHAR(100),
    role NVARCHAR(50),      
    content NVARCHAR(MAX),  
    score FLOAT NULL,       
    created_at DATETIME DEFAULT GETDATE()
); 
GO

-- 4. Başlangıç Kullanıcıları
INSERT INTO Users (username, password_hash, full_name, role)
VALUES ('admin', '123456', 'Sistem Yöneticisi', 'admin'),
       ('destek_uzmani', '123456', 'Ahmet Yılmaz', 'technician');
GO