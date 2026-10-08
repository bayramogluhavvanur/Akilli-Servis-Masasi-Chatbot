import os
import psycopg2
from dotenv import load_dotenv
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer

# ============================================================
# 1. ORTAM DEĞİŞKENLERİ VE GEMINI CLIENT
# ============================================================

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError(".env dosyasında GEMINI_API_KEY bulunamadı.")

ai_client = genai.Client(api_key=api_key)

print("[-] Vektör modeli belleğe yükleniyor...")
embed_model = SentenceTransformer(
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)


# ============================================================
# 2. VERİTABANI BAĞLANTISI (PostgreSQL / pgvector)
# ============================================================

def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        port="5432",
        dbname="servis_masasi_db",
        user="postgres",
        password="admin123",
    )


# ============================================================
# 3. İLGİLİ KAYITLARI GETİR (PostgreSQL Vektör Arama)
# ============================================================

def retrieve_relevant_tickets(query: str, top_k: int = 5):
    print("\n" + "=" * 70)
    print(f"[RAG] Kullanıcı sorusu: {query}")

    query_vector = embed_model.encode(query).tolist()

    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
    SELECT
        source,
        category,
        subject,
        answer,
        1 - (embedding <=> %s::vector) AS similarity
    FROM knowledge_base
    ORDER BY embedding <=> %s::vector
    LIMIT %s;
    """

    cursor.execute(sql, (query_vector, query_vector, top_k))
    rows = cursor.fetchall()

    cursor.close()
    conn.close()

    print(f"[RAG] Bulunan kayıt sayısı: {len(rows)}")

    for i, row in enumerate(rows, 1):
        print(
            f"[RAG] {i}. "
            f"Kategori={row[1]} | "
            f"Konu={row[2]} | "
            f"Similarity={float(row[4]):.4f}"
        )

    print("=" * 70)
    return rows


# ============================================================
# 4. CHAT BAŞLIĞI OLUŞTUR (Gemini ile Akıllı Özet)
# ============================================================

def generate_chat_title(first_message: str) -> str:
    """Kullanıcının ilk sorusundan 3-5 kelimelik Türkçe sohbet başlığı üretir."""
    try:
        prompt = (
            "Aşağıdaki kullanıcı sorusunu analiz et ve "
            "yan panelde gösterilmek üzere Türkçe, "
            "maksimum 4-5 kelimelik, net bir konu başlığı oluştur. "
            "Tırnak işareti, nokta veya açıklama ekleme. "
            "Sadece başlığı yaz.\n\n"
            f"Soru: {first_message}"
        )

        response = ai_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        title = response.text.strip().replace('"', "").replace("'", "")
        return title[:40] if title else first_message[:30] + "..."

    except Exception as e:
        print(f"[!] Başlık özetleme hatası: {e}")
        return first_message[:30] + "..."


# ============================================================
# 5. HELPDESK CEVABI ÜRET (RAG + Fallback Model Yapısı)
# ============================================================

def generate_helpdesk_response(user_query: str,chat_history: list = None):
  relevant_docs = retrieve_relevant_tickets(user_query, top_k=5)

  if not relevant_docs:
    return (
        "Bilgi bankasında bu konuyla ilgili eşleşen bir kayıt bulunamadı.",
        [],
    )

  # Ağırlıklı kategoriyi tespit edip uzman personasını belirliyoruz
  categories = [row[1] for row in relevant_docs]  # row[1] -> category
  is_oracle = any("Oracle" in str(c) for c in categories)
  is_windows = any("Windows" in str(c) for c in categories)

  if is_oracle:
    persona_directive = (
        "ROL: Sen Kıdemli bir Oracle DBA'sin. Yanıtında mutlaka uygulanabilir "
        "SQL sorguları, Tablespace yönetim komutları veya RMAN kod blokları sun."
    )
  elif is_windows:
    persona_directive = (
        "ROL: Sen Kıdemli bir Windows Server Uzmanısın (Active Directory, IIS, "
        "Event Log). Yanıtında mutlaka net PowerShell komutları veya cmd"
        " blokları sun."
    )
  else:
    persona_directive = (
        "ROL: Sen Kurumsal BT Servis Masası Asistanısın. Çözüm adımlarını net "
        "ve teknik olarak sırala."
    )

  context_blocks = []
  for idx, (source, category, subject, answer, sim) in enumerate(
      relevant_docs, 1
  ):
    context_blocks.append(
        f"--- Referans Doküman {idx} ---\n"
        f"Kaynak: {source}\n"
        f"Kategori: {category}\n"
        f"Konu: {subject}\n"
        f"Çözüm/Cevap: {answer}\n"
        f"Benzerlik: {sim:.4f}\n"
    )

  full_context = "\n".join(context_blocks)

  prompt = f"""
{persona_directive}

Aşağıda veritabanından çekilen teknik referans dokümanları bulunmaktadır:
{full_context}

KULLANICI SORUSU:
{user_query}

Lütfen yukarıdaki referans dokümanlara ve uzmanlık alanına dayanarak kullanıcıya Türkçe ve teknik olarak doğru bir yanıt ver.

Yanıt formatı:
1. Sorunun teknik nedeni
2. Adım adım çözüm adımları
3. Uygulanabilir Kod / SQL / PowerShell örneği
4. Kullanılan kaynaklar

ÖNEMLİ:
- Referanslarda olmayan bilgileri kesin gerçekmiş gibi uydurma.
- Emin olmadığın bilgileri açıkça belirt.
- Kaynak bilgisini yalnızca verilen referans dokümanlardan üret.
- Gereksiz uzun cevap verme.
"""

  oncelikli_modeller = [
      "gemini-3.8-flash",  # Google API uyarısında önerilen en güncel flash model
      "gemini-3.5-flash-lite",  # Hızlı ve hafif alternatif model
      "gemini-2.0-flash",  # Kararlı yedek model
      "gemini-1.5-flash",  # Klasik yedek model
  ]

  config = types.GenerateContentConfig(
      tool_config=types.ToolConfig(
          function_calling_config=types.FunctionCallingConfig(mode="NONE")
      )
  )

  last_error = None
  for model_name in oncelikli_modeller:
    try:
      print(f"[-] Gemini modeli deneniyor: {model_name}")
      response = ai_client.models.generate_content(
          model=model_name, contents=prompt, config=config
      )
      # Başarılı olduğunda yanıtı ve kaynakları dönüyoruz (Return burada olmalı)
      if response and response.text:
        return response.text, relevant_docs
    except Exception as e:
      print(f"[!] {model_name} hata verdi ({e.__class__.__name__}): {e}")
      last_error = e
      continue

  # Eğer tüm modeller hata verirse None yerine uyarı mesajı dönüyoruz
  return (
      "Model servislerine erişilemedi. Detaylı hata:"
      f" {last_error}", relevant_docs
  )


if __name__ == "__main__":
  test_soru = (
      "ORA-00942 table or view does not exist hatası alıyorum, nasıl"
      " düzeltebilirim?"
  )
  print(f"\n[?] Soru: {test_soru}\n" + "=" * 60)
  cevap, kaynaklar = generate_helpdesk_response(test_soru)
  print("\n[AI Yanıtı]:\n")
  print(cevap)