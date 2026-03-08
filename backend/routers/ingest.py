import logging
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.graphs.ingestion_graph import ingestion_app
from backend.schemas.models import IngestRequestModel
# Updated Import: Using the new Singleton Bus
from backend.clients.supabase_client import supabase_bus

logger = logging.getLogger(__name__)
ingest_router = APIRouter()

@ingest_router.post("/api/v1/ingest")
async def run_ingestion(request: IngestRequestModel):
    try:
        # UPDATED: Get the managed client from our singleton bus
        supabase = supabase_bus.get_client()

        # 1. VALIDATION & STATE RETRIEVAL
        job_result = (
            await supabase.table("ingestion_jobs")
            .select("id, user_id, document_id, status")
            .eq("id", request.job_id)
            .eq("user_id", request.user_id)
            .limit(1)
            .execute()
        )

        if not job_result.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingestion job not found."
            )

        job = job_result.data[0]
        job_status = job["status"]

        # 2. EARLY EXIT (Saves processing costs if already done)
        if job_status == "done":
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "message": "This document has already been fully processed.",
                    "user_id": request.user_id,
                    "job_id": request.job_id,
                    "document_id": job["document_id"],
                    "current_stage": job_status,
                    "graph_status": "done",
                    "chroma_count": 0,
                    "elastic_count": 0,
                    "error": None,
                    "error_stage": None,
                }
            )

        # 3. GRAPH EXECUTION (The "Heavy Lifting")
        # Initialize the state to be passed through the LangGraph nodes
        graph_initial_state = {
            "user_id": request.user_id,
            "job_id": request.job_id,
            "document_id": job["document_id"],
            "status": job_status,
        }

        # Invoke the graph with LangSmith tracing and persistence configuration
        graph_result = await ingestion_app.ainvoke(
            graph_initial_state,
            config={
                "run_name": f"ingestion_job_{request.job_id}",
                "tags": [
                    "ingestion",
                    "rag",
                    f"user:{request.user_id}",
                    f"job:{request.job_id}",
                ],
                "metadata": {
                    "job_id": request.job_id,
                    "user_id": request.user_id,
                    "document_id": job["document_id"],
                    "thread_id": request.job_id,
                    "pipeline": "rag_ingestion",
                },
                "configurable": {
                    "thread_id": request.job_id, # Key for state persistence/resuming
                },
            },
        )

        # 4. ERROR HANDLING (Graph Level)
        if graph_result.get("status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "message": "Ingestion graph failed.",
                    "user_id": request.user_id,
                    "job_id": request.job_id,
                    "document_id": job["document_id"],
                    "current_stage": job_status,
                    "error": graph_result.get("error"),
                    "error_stage": graph_result.get("error_stage"),
                }
            )

        # 5. SUCCESS RESPONSE
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "message": "Ingestion graph executed successfully.",
                "user_id": request.user_id,
                "job_id": request.job_id,
                "document_id": job["document_id"],
                "current_stage": job_status,
                "graph_status": graph_result.get("status"),
                "chroma_count": graph_result.get("chroma_count", 0),
                "elastic_count": graph_result.get("elastic_count", 0),
                "error": graph_result.get("error"),
                "error_stage": graph_result.get("error_stage"),
            }
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.errors()[0]["msg"]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in ingestion route: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred."
        )