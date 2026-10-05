
import argparse
import re

import pandas as pd

# --- Ayarlar (gerekirse buradan değiştir) -----------------------------------
LANGUAGE = "en"
QUEUES = ["Technical Support", "IT Support", "Service Outages and Maintenance"]
MIN_ANSWER_CHARS = 100
# <name>, <tel_num> gibi anonimleştirme yer tutucuları
PLACEHOLDER = re.compile(r"<[a-z_ ]+>", re.IGNORECASE)
# -----------------------------------------------------------------------------


def clean_text(value: str) -> str:
    """Metindeki '\\n' kaçışlarını gerçek satır sonuna çevirir, boşlukları toparlar."""
    value = str(value).replace("\\n", "\n").replace("\r", "")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/aa_dataset-tickets-multi-lang-5-2-50-version.csv")
    parser.add_argument("--output", default="data/tickets.csv")
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    df["ticket_id"] = df.index  # orijinal dosyadaki satır numarası (izlenebilirlik için)
    print(f"1) Ham veri                          : {len(df):>6}")

    df = df[df["language"] == LANGUAGE]
    print(f"2) Dil = {LANGUAGE}                          : {len(df):>6}")

    df = df[df["queue"].isin(QUEUES)]
    print(f"3) BT ile ilgili kuyruklar           : {len(df):>6}")

    df = df.dropna(subset=["body", "answer"]).copy()
    print(f"4) body ve answer dolu               : {len(df):>6}")

    for col in ["subject", "body", "answer"]:
        df[col] = df[col].fillna("").map(clean_text)

    df = df[df["answer"].str.len() >= MIN_ANSWER_CHARS]
    print(f"5) Cevap >= {MIN_ANSWER_CHARS} karakter             : {len(df):>6}")

    df = df[~df["answer"].str.contains(PLACEHOLDER)]
    df = df[~df["body"].str.contains(PLACEHOLDER)]
    print(f"6) Yer tutucu (<name> vb.) yok       : {len(df):>6}")

    df = df.drop_duplicates(subset=["body"]).drop_duplicates(subset=["answer"])
    print(f"7) Tekrarlı kayıtlar atıldı          : {len(df):>6}")

    # Etiketleri tek sütunda topla
    tag_cols = [c for c in df.columns if c.startswith("tag_")]
    df["tags"] = df[tag_cols].apply(lambda r: ", ".join(str(t) for t in r if pd.notna(t)), axis=1)

    # Embedding'e girecek tek metin (chunk'lama bu alandan yapılacak)
    df["content"] = (
        "Subject: " + df["subject"].replace("", "(no subject)")
        + "\nProblem: " + df["body"]
        + "\nSolution: " + df["answer"]
    )

    out_cols = ["ticket_id", "subject", "body", "answer", "type", "queue", "priority", "tags", "content"]
    df[out_cols].to_csv(args.output, index=False, encoding="utf-8")

    print(f"\nKaydedildi: {args.output}  ({len(df)} kayıt)")
    print("\nKuyruk dağılımı:")
    print(df["queue"].value_counts().to_string())
    print("\n'content' alanı uzunluğu (karakter): "
          f"ort={int(df['content'].str.len().mean())}, maks={df['content'].str.len().max()}")


if __name__ == "__main__":
    main()
