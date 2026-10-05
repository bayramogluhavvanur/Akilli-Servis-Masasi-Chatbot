import os
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer

# 1. Docker PostgreSQL Bağlantısı
conn = psycopg2.connect(
    host="localhost",
    port="5432",
    dbname="servis_masasi_db",
    user="postgres",
    password="admin123"
)
cursor = conn.cursor()

# 2. Ortak Tabloyu Oluştur
cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
cursor.execute("""
CREATE TABLE IF NOT EXISTS knowledge_base (
    id SERIAL PRIMARY KEY,
    source VARCHAR(50),
    external_id VARCHAR(100),
    category VARCHAR(100),
    tags TEXT,
    subject TEXT,
    body TEXT,
    answer TEXT,
    content TEXT,
    embedding vector(384)
);
""")
conn.commit()
print("[✓] 'knowledge_base' tablosu hazırlandı.")

# 3. Embedding Modelini Yükle
print("[-] Hugging Face modeli yükleniyor (all-MiniLM-L6-v2)...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# 4. Dosya Tanımları ve Eşleştirmeler
# NOT: Dosya isimlerinizi buradaki 'file' alanlarına göre düzenleyin!
file_configs = [
    {
        "file": os.path.join("data", "kaggle_tickets.csv"),
        "default_source": "kaggle_itsm",
        "id_col": "ticket_id",
        "cat_col": "queue",
        "tags_col": "tags",
        "subj_col": "subject",
        "body_col": "body",
        "ans_col": "answer",
        "content_col": "content"
    },
    {
        "file": os.path.join("data", "se_windows.csv"),
        "default_source": "se_windows",
        "id_col": "source_id",
        "cat_col": "category",
        "tags_col": "category",
        "subj_col": None,
        "body_col": "body",
        "ans_col": "answer",
        "content_col": "content"
    },
    {
        "file": os.path.join("data", "se_oracle.csv"),
        "default_source": "se_oracle",
        "id_col": "source_id",
        "cat_col": "category",
        "tags_col": "category",
        "subj_col": None,
        "body_col": "body",
        "ans_col": "answer",
        "content_col": "content"
    }
]

# 5. Dosyaları Sırayla Oku, Vektörleştir ve Ekle
for cfg in file_configs:
    file_path = cfg["file"]
    
    if not os.path.exists(file_path):
        print(f"[!] {file_path} bulunamadı, atlanıyor.")
        continue

    print(f"\n[+] {file_path} işleniyor...")
    df = pd.read_csv(file_path)

    # Eksik değerleri temizle
    for col in df.columns:
        df[col] = df[col].fillna("").astype(str)

    # Vektörleştirilecek metni belirle (content boşsa gövde ve yanıtı birleştir)
    text_to_embed = []
    for _, row in df.iterrows():
        txt = row.get(cfg["content_col"], "").strip()
        if not txt:
            txt = f"Soru: {row.get(cfg['body_col'], '')}\nCevap: {row.get(cfg['ans_col'], '')}"
        text_to_embed.append(txt)

    # Hugging Face ile Vektör Üretimi
    print(f"[-] {len(df)} kayıt için 384 boyutlu vektörler üretiliyor...")
    embeddings = model.encode(text_to_embed, batch_size=64, show_progress_bar=True)

    # Veritabanına Yazma
    print("[-] Veritabanına kaydediliyor...")
    records = []
    for i, row in df.iterrows():
        src = row.get("source", "") if "source" in row and row["source"] else cfg["default_source"]
        subj = row.get(cfg["subj_col"], "") if cfg["subj_col"] else ""
        
        records.append((
            src,
            row.get(cfg["id_col"], ""),
            row.get(cfg["cat_col"], ""),
            row.get(cfg["tags_col"], ""),
            subj,
            row.get(cfg["body_col"], ""),
            row.get(cfg["ans_col"], ""),
            text_to_embed[i],
            embeddings[i].tolist()
        ))

    insert_query = """
    INSERT INTO knowledge_base 
    (source, external_id, category, tags, subject, body, answer, content, embedding)
    VALUES %s;
    """
    execute_values(cursor, insert_query, records, page_size=500)
    conn.commit()
    print(f"[✓] {file_path} içinden {len(records)} kayıt başarıyla eklendi.")

cursor.close()
conn.close()
print("\n[TAMAMLANDI] Tüm CSV dosyaları ve vektörleri başarıyla PostgreSQL'e aktarıldı!")