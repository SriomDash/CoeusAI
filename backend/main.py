import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.clients.groq_client import groq_bus
from backend.clients.gemini_client import gemini_bus
from backend.clients.cohere_client import co_bus
from backend.clients.supabase_client import supabase_bus
from backend.clients.chroma_client import chroma_bus
from backend.clients.elastic_search_client import elastic_bus

from backend.routers.user import user_router
from backend.routers.upload import upload_router
from backend.routers.ingest import ingest_router

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address


# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("coeus_ai")


# -------- Rate Limit Key (main.py only) --------
def smart_key_func(request: Request) -> str:
    """
    Global key:
    - If user_id is provided as query param, rate limit per user
    - else fallback to IP
    """
    user_id = request.query_params.get("user_id")
    if user_id and user_id != "default_user":
        return f"user:{user_id}"
    return f"ip:{get_remote_address(request)}"


# Create ONE limiter only (this one is used everywhere)
limiter = Limiter(
    key_func=smart_key_func,
    default_limits=["10/minute"],
)


# --- Lifespan: The Server Guard ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Coeus AI: Initializing modular client buses...")
        await elastic_bus.connect()

        app.state.groq = groq_bus
        app.state.gemini = gemini_bus
        app.state.cohere = co_bus
        app.state.supabase = supabase_bus
        app.state.chroma = chroma_bus
        app.state.elastic = elastic_bus

        logger.info("All clients connected and attached to state.")
        yield
    except Exception as e:
        logger.error(f"FATAL STARTUP ERROR: {e}")
        raise e
    finally:
        logger.info("Coeus AI: Shutting down services...")
        await elastic_bus.close()


# --- App Initialization ---
app = FastAPI(
    title=settings.APP_TITLE,
    description=settings.APP_DESCRIPTION,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Wire SlowAPI AFTER limiter is defined
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


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
    required_clients = ['groq', 'gemini', 'cohere', 'supabase', 'chroma', 'elastic']
    buses_loaded = all(hasattr(app.state, client) for client in required_clients)

    es_ping = False
    if hasattr(app.state, 'elastic'):
        try:
            es_ping = await app.state.elastic.client.ping()
        except Exception:
            es_ping = False

    is_healthy = buses_loaded and es_ping

    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if is_healthy else "degraded",
            "components": {
                "system_buses": "ok" if buses_loaded else "error",
                "elasticsearch_connection": "ok" if es_ping else "unreachable"
            }
        }
    )

# --- Mount Routers ---
app.include_router(user_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")