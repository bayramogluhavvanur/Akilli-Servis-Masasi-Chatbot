from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"mesaj": "Merhaba, servis masası chatbot!"}