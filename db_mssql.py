import json
import re
import bcrypt
import pyodbc

# Docker MSSQL Bağlantı Dizesi
CONN_STR = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=localhost,1433;"
    "DATABASE=ServisMasasi_Auth;"
    "UID=sa;"
    "PWD=ServisMasasi2026!;"
    "TrustServerCertificate=yes;"
)


def validate_user_credentials(email, password):
    """E-posta ve şifre kurallarını kontrol eder."""
    email_regex = r"^[\w\.-]+@[\w\.-]+\.\w+$"
    if not re.match(email_regex, email):
        return False, "Geçersiz e-posta formatı! (Örn: kullanıcı@sirket.com)"

    if len(password) < 8:
        return False, "Şifre en az 8 karakter olmalıdır!"
    if not re.search(r"[A-Z]", password):
        return False, "Şifre en az bir büyük harf içermelidir!"
    if not re.search(r"[a-z]", password):
        return False, "Şifre en az bir küçük harf içermelidir!"
    if not re.search(r"[0-9]", password):
        return False, "Şifre en az bir rakam içermelidir!"

    return True, "Geçerli"


def hash_password(plain_password: str) -> str:
    """Şifreyi Salted Hash (bcrypt) ile şifreler."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Girilen şifre ile veritabanındaki hash'i karşılaştırır."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except Exception:
        return False


def get_connection():
    return pyodbc.connect(CONN_STR, timeout=10)


def register_user(username, email, password, full_name, role="user"):
    """Güvenlik kurallarıyla ve email adresiyle yeni kullanıcı kaydeder."""
    # 1. E-posta ve Şifre Güvenlik Validasyonu
    is_valid, msg = validate_user_credentials(email, password)
    if not is_valid:
        return False, msg

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Kullanıcı adı kontrolü
        cursor.execute(
            "SELECT user_id FROM Users WHERE username = ?", (username.strip(),)
        )
        if cursor.fetchone():
            return False, "Bu kullanıcı adı zaten alınmış."

        # E-posta kontrolü (Aynı e-posta ile tekrar kayıt engellensin)
        cursor.execute("SELECT user_id FROM Users WHERE email = ?", (email.strip(),))
        if cursor.fetchone():
            return False, "Bu e-posta adresi zaten kullanımda."

        # 2. Şifreyi Hash'le
        hashed_pass = hash_password(password)

        # 3. Veritabanına email ile birlikte kaydet
        cursor.execute(
            """
            INSERT INTO Users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                username.strip(),
                email.strip(),
                hashed_pass,
                full_name.strip(),
                role,
            ),
        )
        conn.commit()
        cursor.close()
        return True, "Kayıt başarılı! Şimdi giriş yapabilirsiniz."
    except Exception as e:
        return False, f"Veritabanı hatası: {e}"
    finally:
        if conn:
            conn.close()


def authenticate_user(username, password):
    """Kullanıcı girişi ve bcrypt doğrulaması."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT user_id, username, password_hash, full_name, role 
            FROM Users 
            WHERE username = ?
        """,
            (username.strip(),),
        )
        row = cursor.fetchone()
        cursor.close()

        if row:
            db_user_id, db_user, db_hash, db_name, db_role = row
            # 3. Bcrypt ile Şifre Doğrulama
            if verify_password(password.strip(), db_hash):
                return {
                    "user_id": db_user_id,
                    "username": db_user,
                    "full_name": db_name,
                    "role": db_role,
                }
        return None
    except Exception as e:
        print(f"[!] MSSQL Giriş Hatası: {e}")
        return None
    finally:
        if conn:
            conn.close()


def create_chat_session(user_id, title="Yeni Destek Talebi"):
    """Yeni sohbet oturumu açar."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ChatSessions (user_id, session_title) 
            OUTPUT INSERTED.session_id 
            VALUES (?, ?)
            """,
            (user_id, title),
        )
        session_id = cursor.fetchone()[0]
        conn.commit()
        cursor.close()
        return session_id
    except Exception as e:
        print(f"[!] Session Oluşturma Hatası: {e}")
        return None
    finally:
        if conn:
            conn.close()


def log_message(session_id, role, content, sources=None, score=None):
    """Mesajları veritabanına kaydeder."""

    # 1. Tuzak kontrolü: Oturum ID boş mu?
    if not session_id:
        print(f"[!] UYARI: session_id boş/None olduğu için loglanamadı! (Rol: {role})")
        return

    if not content or str(content).strip() == "":
        content = "[Boş Mesaj]"

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO ChatLogs (session_id, role, content, score)
            VALUES (?, ?, ?, ?)
            """,
            (session_id, role, content, score),
        )

        conn.commit()
        cursor.close()
        print(f"[+] Başarıyla Veritabanına Yazıldı -> [{role}]: {content[:30]}...")

    except Exception as e:
        print(f"[!] Loglama Kritik Hatası: {e}")
    finally:
        if conn:
            conn.close()


def update_session_title_if_default(session_id, summary_title):
    """Gemini tarafından üretilen özet başlığı MSSQL veritabanına kaydeder."""
    if not session_id or not summary_title:
        return

    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE ChatSessions 
            SET session_title = ? 
            WHERE session_id = ? AND (session_title LIKE 'Destek Talebi%' OR session_title LIKE 'Yeni Destek%' OR session_title LIKE 'Yeni Sohbet%')
            """,
            (summary_title, session_id),
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"[!] Başlık güncelleme hatası: {e}")
    finally:
        if conn:
            conn.close()


def get_user_chat_sessions(user_id):
    """Kullanıcının geçmiş tüm sohbet oturumlarını getirir."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
        SELECT session_id, session_title, started_at 
        FROM ChatSessions 
        WHERE user_id = ? 
        ORDER BY started_at DESC
            """,
            (user_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [{"session_id": r[0], "title": r[1], "date": r[2]} for r in rows]
    except Exception as e:
        print(f"[!] Geçmiş oturumları çekme hatası: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_session_messages(session_id):
    """Belirli bir oturuma ait tüm mesajları getirir."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content 
            FROM ChatLogs 
            WHERE session_id = ? 
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        cursor.close()

        messages = []
        for r in rows:
            # r[0] -> role, r[1] -> content (2 elemanlı yapı güvenle işleniyor)
            messages.append({"role": r[0], "content": r[1]})

        return messages
    except Exception as e:
        print(f"[!] Oturum mesajlarını çekme hatası: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_all_logs_for_admin():
    """Admin paneli için logları çeker."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Yeni tablo (ChatLogs) ve yeni sütunlar (role, content, score) ile güncellendi
        query = """
            SELECT TOP 50 
                u.username, u.full_name, s.session_id, 
                l.role, l.content, l.score, l.created_at
            FROM ChatLogs l
            JOIN ChatSessions s ON l.session_id = s.session_id
            JOIN Users u ON s.user_id = u.user_id
            ORDER BY l.created_at DESC;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        cursor.close()
        return rows

    except Exception as e:
        print(f"[!] Log Çekme Hatası: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_top_questions(limit=5):
    """En sık sorulan kullanıcı sorularını getirir."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        # Kullanıcı mesajlarını gruplayıp en çok tekrar edenleri sayıyoruz
        cursor.execute(f"""
            SELECT TOP ({limit}) content, COUNT(*) as soru_sayisi
            FROM ChatLogs
            WHERE role = 'user'
            GROUP BY content
            ORDER BY soru_sayisi DESC
            """)
        rows = cursor.fetchall()
        sonuc_listesi = []
        for row in rows:
            sonuc_listesi.append((row[0], row[1]))

        return sonuc_listesi
    except Exception as e:
        print(f"[!] En çok sorulan sorular alınamadı: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_chatbot_metrics():
    """Chatbot başarı oranı, toplam etkileşim ve ortalama benzerlik skorunu hesaplar."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # DÜZELTME 1: CASE WHEN içindeki score değerini de FLOAT'a dönüştürdük (CAST).
        cursor.execute("""
            SELECT 
                COUNT(*) as toplam_yanit,
                AVG(CAST(score AS FLOAT)) as ortalama_skor,
                SUM(CASE WHEN CAST(score AS FLOAT) >= 0.75 THEN 1 ELSE 0 END) as basarili_yanit_sayisi
            FROM ChatLogs
            WHERE role = 'assistant' AND score IS NOT NULL
            """)
        row = cursor.fetchone()
        cursor.close()

        if row:
            toplam = row[0] or 0
            ort_skor = row[1] or 0.0
            basarili = row[2] or 0

            # Başarı yüzdesi (Örn: 0.75 ve üzeri benzerlik skorunu başarılı sayıyoruz)
            basari_orani = (basarili / toplam * 100) if toplam > 0 else 0.0

            return {
                "toplam_yanit": toplam,
                "ortalama_skor": ort_skor,
                "basari_orani": basari_orani,
            }

        return {"toplam_yanit": 0, "ortalama_skor": 0.0, "basari_orani": 0.0}

    # DÜZELTME 2: Python'un çökmesini engelleyen hata yakalama bloğu eklendi.
    except Exception as e:
        print(f"Metrikler çekilirken hata oluştu: {e}")
        return {"toplam_yanit": 0, "ortalama_skor": 0.0, "basari_orani": 0.0}

    # DÜZELTME 3: Veritabanı bağlantısı garanti olarak kapatılarak performans düşüşü önlendi.
    finally:
        if conn:
            conn.close()
