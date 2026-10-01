"""
02_fetch_stackexchange.py
HuggingFaceH4/stack-exchange-preferences veri setinden, tüm 22 GB'ı indirmeden
(streaming ile) belirli bir siteden anahtar kelimeye uyan soru-cevapları çeker.

Kurulum:   pip install datasets pandas
Örnekler (proje klasöründen):
    python scripts/02_fetch_stackexchange.py --site serverfault.com --category windows_server
    python scripts/02_fetch_stackexchange.py --site dba.stackexchange.com --category oracle
İlk denemede küçük bir örnekle test et:
    python scripts/02_fetch_stackexchange.py --site dba.stackexchange.com --category oracle --limit 20

NOT: Alan adları (question, answers, pm_score, text, qid) veri setinin README'sindeki
koda dayanır. İlk çalıştırmada ekrana bir örnek kayıt basılır; alan adları farklıysa
FIELD_* sabitlerini düzelt.
"""
import argparse
import html
import re

import pandas as pd
from datasets import load_dataset

REPO = "HuggingFaceH4/stack-exchange-preferences"

# Kategori başına aranacak anahtar kelimeler (soru metninde, küçük harfle eşleşir)
KEYWORDS = {
    "windows_server": [
        "active directory", "windows server", " iis ", "group policy", "gpo",
        "event viewer", "event log", "powershell", "domain controller", "dns server",
    ],
    "oracle": [
        "oracle", "tablespace", "rman", "ora-0", "ora-1", "pl/sql", "expdp", "impdp",
        "awr", "execution plan", "dbms_",
    ],
}

FIELD_QUESTION = "question"
FIELD_ANSWERS = "answers"
FIELD_SCORE = "pm_score"
FIELD_TEXT = "text"
FIELD_QID = "qid"

MIN_ANSWER_CHARS = 150
MAX_CONTENT_CHARS = 3000  # çok uzun kayıtları atla (chunk'lamayı kolaylaştırır)


def strip_html(text: str) -> str:
    """HTML etiketlerini temizler, kod bloklarını ``` ile korur."""
    text = re.sub(r"<pre[^>]*>\s*(?:<code[^>]*>)?(.*?)(?:</code>)?\s*</pre>",
                  lambda m: "\n```\n" + m.group(1) + "\n```\n", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--site", required=True, help="örn. serverfault.com veya dba.stackexchange.com")
    p.add_argument("--category", required=True, choices=list(KEYWORDS))
    p.add_argument("--limit", type=int, default=3000, help="en fazla kaç kayıt toplansın")
    p.add_argument("--max-scan", type=int, default=400_000, help="en fazla kaç kayıt taransın")
    p.add_argument("--output", default=None)
    args = p.parse_args()
    output = args.output or f"data/se_{args.category}.csv"

    ds = load_dataset(REPO, data_dir=f"data/{args.site}", split="train", streaming=True)

    rows, scanned = [], 0
    for item in ds:
        scanned += 1
        if scanned == 1:
            print("Örnek kaydın alanları:", list(item.keys()))
        if scanned > args.max_scan or len(rows) >= args.limit:
            break

        question_raw = item.get(FIELD_QUESTION) or ""
        q_lower = " " + question_raw.lower() + " "
        if not any(k in q_lower for k in KEYWORDS[args.category]):
            continue

        answers = item.get(FIELD_ANSWERS) or []
        if not answers:
            continue
        best = max(answers, key=lambda a: a.get(FIELD_SCORE, -99))
        if best.get(FIELD_SCORE, -99) < 1:  # olumlu oy almamış cevapları alma
            continue

        question = strip_html(question_raw)
        answer = strip_html(best.get(FIELD_TEXT) or "")
        if len(answer) < MIN_ANSWER_CHARS:
            continue

        content = f"Problem: {question}\nSolution: {answer}"
        if len(content) > MAX_CONTENT_CHARS:
            continue

        qid = item.get(FIELD_QID)
        rows.append({
            "source": args.site,
            "source_id": qid,
            "url": f"https://{args.site}/questions/{qid}" if qid else "",
            "category": args.category,
            "body": question,
            "answer": answer,
            "score": best.get(FIELD_SCORE),
            "content": content,
        })

    df = pd.DataFrame(rows)
    df.to_csv(output, index=False, encoding="utf-8")
    print(f"Taranan: {scanned}  |  Seçilen: {len(df)}  |  Kaydedildi: {output}")


if __name__ == "__main__":
    main()
