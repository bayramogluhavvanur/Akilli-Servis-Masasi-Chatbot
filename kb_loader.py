import pandas as pd, psycopg2
from psycopg2.extras import execute_values
from sentence_transformers import SentenceTransformer
from config import PG

_model = None
def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    return _model

def chunk_text(text, size=400, overlap=60):
    text = (text or "").strip()
    if len(text) <= size:
        return [text] if text else []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            cut = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if cut > start + size // 2:
                end = cut + 1
        chunks.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - overlap
    return [c for c in chunks if c]

def ingest_dataframe(df, source, subject_col, answer_col, category,
                     table="knowledge_base_v2"):
    conn = psycopg2.connect(**PG); cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {table} (
        id SERIAL PRIMARY KEY, source TEXT, category TEXT, subject TEXT,
        answer TEXT, chunk_index INT, embedding vector(384));""")
    rows, texts = [], []
    for _, r in df.iterrows():
        subject = str(r.get(subject_col, "")).strip()[:120]
        for i, ch in enumerate(chunk_text(str(r.get(answer_col, "")))):
            rows.append((source, category, subject, ch, i))
            texts.append(f"Kategori: {category} | Konu: {subject} | Çözüm: {ch}")
    if not rows:
        return 0
    vecs = get_model().encode(texts, batch_size=64, show_progress_bar=False)
    execute_values(cur,
        f"INSERT INTO {table} (source, category, subject, answer, chunk_index, embedding) VALUES %s",
        [(*r, v.tolist()) for r, v in zip(rows, vecs)], page_size=500)
    conn.commit(); cur.close(); conn.close()
    return len(rows)

if __name__ == "__main__":
    ingest_dataframe(pd.read_csv("data/kaggle_tickets.csv"), "Kaggle-Tickets", "subject", "answer", "Genel BT")
    ingest_dataframe(pd.read_csv("data/se_windows.csv"), "StackExchange-Windows", "body", "answer", "Windows Server")
    ingest_dataframe(pd.read_csv("data/se_oracle.csv"), "StackExchange-Oracle", "body", "answer", "Oracle DB")