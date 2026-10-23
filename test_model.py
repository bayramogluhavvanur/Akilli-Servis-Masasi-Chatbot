import os
from dotenv import load_dotenv
from google import genai

# .env dosyasını yükle
load_dotenv()

# Sadece 1. API anahtarını alıyoruz
api_key = os.getenv("GEMINI_API_KEY_1")

if not api_key:
    print("API anahtarı bulunamadı! Lütfen .env dosyanı kontrol et.")
else:
    print("API Anahtarınızla kullanılabilen modeller kontrol ediliyor...\n")
    try:
        client = genai.Client(api_key=api_key)
        
        # Hesabının erişebildiği tüm modelleri listele
        models = client.models.list()
        
        for m in models:
            # Sadece içerik üretebilen modelleri ekrana yazdır
            if "generateContent" in m.supported_actions:
                print(f"✅ Desteklenen Model: {m.name}")
                
    except Exception as e:
        print(f"Hata oluştu: {e}")