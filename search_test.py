import psycopg2
from sentence_transformers import SentenceTransformer

# 1. Model ve Veritabanı Bağlantısı
print("[-] Arama modeli yükleniyor...")
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

conn = psycopg2.connect(
    host="localhost",
    port="5432",
    dbname="servis_masasi_db",
    user="postgres",
    password="admin123",
)
cursor = conn.cursor()


def search_knowledge_base(query_text, top_k=3, source_filter=None):
    # Kullanıcı sorusunu 384 boyutlu vektöre çevir
    query_vector = model.encode(query_text).tolist()

    # Kosinüs mesafesi (<=>) ile en yakın eşleşmeleri getir
    if source_filter:
        sql = """
        SELECT source, category, subject, answer, 1 - (embedding <=> %s::vector) AS similarity
        FROM knowledge_base
        WHERE source = %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        cursor.execute(sql, (query_vector, source_filter, query_vector, top_k))
    else:
        sql = """
        SELECT source, category, subject, answer, 1 - (embedding <=> %s::vector) AS similarity
        FROM knowledge_base
        ORDER BY embedding <=> %s::vector
        LIMIT %s;
        """
        cursor.execute(sql, (query_vector, query_vector, top_k))

    return cursor.fetchall()


# 2. Test Sorgusu
ornek_soru = "ORA-00942 table or view does not exist error"
print(f"\n[?] Soru: {ornek_soru}")
print("-" * 60)

sonuclar = search_knowledge_base(ornek_soru, top_k=3)

for idx, (source, category, subject, answer, similarity) in enumerate(
    sonuclar, 1
):
    print(f"\n[{idx}] Benzerlik: %{similarity * 100:.2f} | Kaynak: {source}")
    if category:
        print(f"Kategori: {category}")
    if subject:
        print(f"Konu: {subject}")
    print(f"Çözüm/Cevap:\n{answer[:300]}...\n")

cursor.close()
conn.close()