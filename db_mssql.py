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
    cursor.execute(
        "SELECT user_id FROM Users WHERE email = ?", (email.strip(),)
    )
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


def log_message(session_id, sender, text, sources=None, score=None):
    """Mesajları veritabanına kaydeder."""
    if not session_id:
        return

    conn = None
    try:
        sources_json = None
        if sources:
            sources_list = []
            for src in sources:
                if isinstance(src, (list, tuple)) and len(src) >= 5:
                    sources_list.append({
                        "source": src[0],
                        "category": src[1],
                        "subject": src[2],
                        "similarity": round(float(src[4]), 4),
                    })
                elif isinstance(src, dict):
                    sources_list.append(src)
            sources_json = json.dumps(sources_list, ensure_ascii=False)

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO ChatMessages (session_id, sender, message_text, retrieved_sources, similarity_score)
            VALUES (?, ?, ?, ?, ?)
            """,
            (session_id, sender, text, sources_json, score),
        )
        conn.commit()
        cursor.close()
    except Exception as e:
        print(f"[!] Loglama Hatası: {e}")
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
        return [
            {"session_id": r[0], "title": r[1], "date": r[2]} for r in rows
        ]
    except Exception as e:
        print(f"[!] Geçmiş oturumları çekme hatası: {e}")
        return []
    finally:
        if conn:
            conn.close()


def get_session_messages(session_id):
    """Belirli bir oturuma ait tüm mesajları ve kaynakları getirir."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT sender, message_text, retrieved_sources 
            FROM ChatMessages 
            WHERE session_id = ? 
            ORDER BY created_at ASC
            """,
            (session_id,),
        )
        rows = cursor.fetchall()
        cursor.close()

        messages = []
        for sender, text, sources_json in rows:
            msg = {"role": sender, "content": text}
            if sources_json:
                try:
                    sources_data = json.loads(sources_json)
                    formatted_sources = []
                    for item in sources_data:
                        formatted_sources.append((
                            item.get("source", "Bilinmiyor"),
                            item.get("category", "-"),
                            item.get("subject", "-"),
                            "",
                            item.get("similarity", 0.0),
                        ))
                    msg["sources"] = formatted_sources
                except Exception:
                    pass
            messages.append(msg)
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
        query = """
            SELECT TOP 50 
                u.username, u.full_name, s.session_id, 
                m.sender, m.message_text, m.similarity_score, m.created_at
            FROM ChatMessages m
            JOIN ChatSessions s ON m.session_id = s.session_id
            JOIN Users u ON s.user_id = u.user_id
            ORDER BY m.created_at DESC;
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