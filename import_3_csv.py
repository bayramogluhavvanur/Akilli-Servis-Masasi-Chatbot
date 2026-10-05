import os
import pandas as pd
import psycopg2
from sentence_transformers import SentenceTransformer
from sympy import content

# 1. Multilingual Embedding Modeli
print("[-] Multilingual Vektör modeli yükleniyor...")
embed_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


# 2. PostgreSQL Bağlantısı
def get_db_connection():
  return psycopg2.connect(
      host="localhost",
      port="5432",
      dbname="servis_masasi_db",
      user="postgres",
      password="admin123",
  )


# 3. Tabloyu Temizle ve Hazırla
# 3. Tabloyu Temizle ve Hazırla
def setup_database():
  conn = get_db_connection()
  cursor = conn.cursor()
  cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")

  # Tablo yoksa oluştur (sütun tiplerini TEXT yaparak uzunluk sınırını kaldırıyoruz)
  create_table_sql = """
    CREATE TABLE IF NOT EXISTS knowledge_base (
        id SERIAL PRIMARY KEY,
        source TEXT,
        category TEXT,
        subject TEXT,
        answer TEXT,
        embedding vector(384)
    );
    """
  cursor.execute(create_table_sql)

  # Mevcut tablodaki kolon limitlerini esnet
  cursor.execute("ALTER TABLE knowledge_base ALTER COLUMN category TYPE TEXT;")
  cursor.execute("ALTER TABLE knowledge_base ALTER COLUMN source TYPE TEXT;")

  # Yeni modelle sıfırdan doldurmak için mevcut verileri temizliyoruz
  cursor.execute("TRUNCATE TABLE knowledge_base;")
  conn.commit()
  cursor.close()
  conn.close()
  print("[+] Veritabanı ve tablo uzunluk limitleri esnetildi, hazırlandı.")


# 4. CSV Dosyasını Okuyup Aktarma Fonksiyonu
def process_and_insert_csv(
    file_path, default_category, source_name, col_mapping
):
  if not os.path.exists(file_path):
    print(f"[!] UYARI: '{file_path}' dosyası bulunamadı, atlanıyor.")
    return

  print(f"\n[-] '{file_path}' işleniyor ({source_name})...")

  # CSV Okuma
  try:
    df = pd.read_csv(file_path)
  except Exception as e:
    print(f"[!] Dosya okuma hatası: {e}")
    return

  conn = get_db_connection()
  cursor = conn.cursor()
  inserted = 0

  for _, row in df.iterrows():
    # Esnek Kolon Eşleme
    subj_col = col_mapping.get("subject", "title")
    ans_col = col_mapping.get("answer", "body")
    cat_col = col_mapping.get("category", None)

    subject = str(row.get(subj_col, "Konu Belirtilmedi"))
    answer = str(row.get(ans_col, ""))
    category = (
        str(row.get(cat_col, default_category)) if cat_col else default_category
    )

    if category == "nan" or not category.strip():
     category = default_category

    # Vektörleştirmek için uzmanlık alanını metne yediriyoruz
    text_to_embed = (
        f"Uzmanlık Kategorisi: {category} | Konu: {subject} | Çözüm: {answer}"
    )
    vector = embed_model.encode(text_to_embed).tolist()

    insert_sql = """
        INSERT INTO knowledge_base (source, category, subject, answer, embedding)
        VALUES (%s, %s, %s, %s, %s::vector);
        """
    cursor.execute(
        insert_sql, (source_name, category, subject, answer, vector)
    )
    inserted += 1

    if inserted % 100 == 0:
      conn.commit()
      print(f"    -> {inserted} kayıt eklendi...")

  conn.commit()
  cursor.close()
  conn.close()
  print(f"[+] {source_name} tamamlandı! Toplam eklenen: {inserted}")


if __name__ == "__main__":
  setup_database()

  # ============================================================
  # 1. ORACLE STACKEXCHANGE CSV (data/se_oracle.csv)
  # ============================================================
  process_and_insert_csv(
      file_path=os.path.join("data", "se_oracle.csv"),
      default_category="Oracle DB",
      source_name="StackExchange-Oracle",
      col_mapping={"source": "source_id", "url": "url", "category": "category", "body": "body", "answer": "answer", "score": "score", "content": "content"},
  )

  # ============================================================
  # 2. WINDOWS STACKEXCHANGE CSV (data/se_windows.csv)
  # ============================================================
  process_and_insert_csv(
      file_path=os.path.join("data", "se_windows.csv"),
      default_category="Windows Server",
      source_name="StackExchange-Windows",
      col_mapping={"source": "source_id", "url": "url", "category": "category", "body": "body", "answer": "answer", "score": "score", "content": "content"},
  )

  # ============================================================
  # 3. KAGGLE BT TICKETS CSV (data/kaggle_tickets.csv)
  # ============================================================
  process_and_insert_csv(
      file_path=os.path.join("data", "kaggle_tickets.csv"),
      default_category="Genel BT",
      source_name="Kaggle-Tickets",
      col_mapping={
          "source": "ticket_id",
          "url": "subject",
          "category": "body",
          "body": "answer",
          "answer": "type",
          "score": "queue",
          "content": "priority"
      },
  )

  print(
      "\n[TEBRİKLER] 'data/' klasöründeki 3 CSV dosyası da yeni Multilingual"
      " model ile veritabanına yüklendi!"
  )