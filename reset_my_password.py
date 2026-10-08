import db_mssql

# 1. Kendi kullanıcı adınızı ve yeni güçlü şifrenizi yazın
KULLANICI_ADI = "admin"  # <-- Burayı değiştirin
YENI_SIFRE = "Admin123,"  # <-- En az 8 karakter, 1 Büyük, 1 Küçük, 1 Rakam içermeli

# 2. Şifreyi salted-bcrypt ile hash'le ve güncelle
hashed_password = db_mssql.hash_password(YENI_SIFRE)

conn = db_mssql.get_connection()
cursor = conn.cursor()

cursor.execute(
    """
    UPDATE Users 
    SET password_hash = ? 
    WHERE username = ?
""",
    (hashed_password, KULLANICI_ADI),
)

conn.commit()
cursor.close()
conn.close()

print(
    f"[+] '{KULLANICI_ADI}' kullanıcısının şifresi başarıyla '{YENI_SIFRE}'"
    " olarak güncellendi!"
)