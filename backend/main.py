import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.clients.groq_client import groq_bus
from backend.clients.gemini_client import gemini_bus
from backend.clients.cohere_client import co_bus
from backend.clients.supabase_client import supabase_bus
from backend.clients.chroma_client import chroma_bus

from backend.routers.user import user_router
from backend.routers.upload import upload_router
# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("coeus_ai")

# --- Lifespan: The Server Guard ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Connects all client buses. If any initialization fails, 
    the server will not start, ensuring production reliability.
    """
    try:
        logger.info(" Coeus AI: Initializing modular client buses...")

        app.state.groq = groq_bus
        app.state.gemini = gemini_bus
        app.state.cohere = co_bus
        app.state.supabase = supabase_bus
        app.state.chroma = chroma_bus

        logger.info("All clients connected and attached to state.")
        yield
    except Exception as e:
        logger.error(f"FATAL STARTUP ERROR: {e}")
        raise e
    finally:
        logger.info(" Coeus AI: Shutting down services...")

# --- App Initialization ---
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Production Routes ---

@app.get("/", tags=["Health"])
async def root() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "app": settings.APP_TITLE,
            "version": settings.APP_VERSION,
            "status": "online"
        }
    )

@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    """
    Verifies that all state-based clients are correctly attached.
    """
    required_clients = ['groq', 'gemini', 'cohere', 'supabase', 'chroma']
    is_ready = all(hasattr(app.state, client) for client in required_clients)
    
    return JSONResponse(
        status_code=status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "healthy" if is_ready else "initializing"}
    )

app.include_router(user_router)
app.include_router(upload_router)