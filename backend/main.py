from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.routers.chat import router as chat_router

app = FastAPI(title="CoeusAI", version="1.0")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(chat_router)

@app.get("/")
async def root():
    return {"message": "Welcome to CoeusAI!"}

@app.get("/health")
async def health():
    return {"status": "healthy"}