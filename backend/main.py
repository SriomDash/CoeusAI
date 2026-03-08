import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
# Updated imports to use your new Bus singletons
from backend.clients.supabase_client import supabase_bus
from backend.clients.elastic_search_client import elastic_bus
from backend.clients.chroma_client import chroma_bus

from backend.routers.upload import upload_router
from backend.routers.ingest import ingest_router

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manages the application lifecycle using the Bus pattern.
    """
    try:
        logger.info("--- SYSTEM BOOT SEQUENCE STARTED ---")

        # 1. Initialize Supabase
        await supabase_bus.connect()
        
        # 2. Initialize Elasticsearch
        await elastic_bus.connect()

        # 3. Initialize ChromaDB
        await chroma_bus.connect()
        # Ensure a collection exists to verify disk/memory access
        chroma_bus.get_collection("startup_healthcheck")
        
        logger.info("--- ALL SYSTEMS OPERATIONAL: COEUIS AI IS ONLINE ---")
        
        # Application runs here...
        yield

    except Exception as e:
        logger.critical(f"BOOT SEQUENCE FAILED: {e}")
        # Raising ensures the server doesn't start in a broken state
        raise e

    finally:
        logger.info("--- INITIATING GRACEFUL SHUTDOWN ---")
        # Standardized cleanup for all services
        await elastic_bus.close()
        await supabase_bus.close()
        await chroma_bus.close()
        logger.info("--- SHUTDOWN COMPLETE ---")


app = FastAPI(
    title=settings.APP_TITLE,
    description="CoeusAI API",
    lifespan=lifespan
)

# Middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def health_check() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "online",
            "services": {
                "supabase": "connected",
                "elasticsearch": "connected",
                "chromadb": "connected"
            }
        }
    )

# Include separate logic modules
app.include_router(upload_router)
app.include_router(ingest_router)