import aiofiles
import asyncio
import os
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

# Import your settings here (adjust the path based on your folder structure)
from backend.config import settings 

from backend.services.pdf_service import PDFService
from backend.services.labeling_service import LabelingService
from backend.services.embedding_service import EmbeddingService
from backend.services.elastic_service import ElasticService
from backend.services.ingestion_tracking_service import IngestionTrackingService


class IngestionState(TypedDict, total=False):
    # Inputs
    file_path: str
    user_id: str
    user_name: str
    job_id: str

    # Internal
    document_id: str
    raw_text: Optional[str]
    pages: List[Dict[str, Any]]
    chunk_records: List[Dict[str, Any]]
    enriched_chunks: List[Dict[str, Any]]

    # Outputs
    chroma_count: int
    elastic_count: int
    status: str
    error: Optional[str]
    error_stage: Optional[str]


async def extract_node(state: IngestionState) -> IngestionState:
    """
    Step 1: Read PDF, extract page-wise text, and create structured chunks.
    """
    print(f"[1/3] Extracting: {state['file_path']}")

    try:
        async with aiofiles.open(state["file_path"], "rb") as f:
            content = await f.read()

        document_id = state["document_id"]

        pages = PDFService.extract_pages(
            filename=state["file_path"],
            raw_bytes=content,
        )

        raw_text = PDFService.extract_raw_text(pages)

        chunk_records = PDFService.chunk_pages(
            pages=pages,
            user_id=state["user_id"],
            job_id=state["job_id"],
            document_id=document_id,
        )

        IngestionTrackingService.update_job_status(
            job_id=state["job_id"],
            status="labeling",
            extracted_pages=len(pages),
            extracted_chunks=len(chunk_records),
        )

        return {
            "document_id": document_id,
            "pages": pages,
            "raw_text": raw_text,
            "chunk_records": chunk_records,
            "status": "extracted",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Extraction Error: {e}")

        IngestionTrackingService.update_job_status(
            job_id=state["job_id"],
            status="failed",
            error_stage="extract",
            error_message=str(e),
            completed=True,
        )

        IngestionTrackingService.update_document_status(
            user_id=state["user_id"],
            document_id=state["document_id"],
            status="failed",
            last_job_id=state["job_id"],
        )

        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "extract",
        }


async def label_node(state: IngestionState) -> IngestionState:
    """
    Step 2: Send structured chunks to labeling service and merge AI metadata.
    """
    if state.get("status") == "failed":
        return state

    print(f"[2/3] Labeling {len(state['chunk_records'])} chunks...")

    try:
        enriched_chunks = await LabelingService.process_and_link(
            chunk_records=state["chunk_records"],
            user_id=state["user_id"],
            job_id=state["job_id"],
        )

        IngestionTrackingService.update_job_status(
            job_id=state["job_id"],
            status="storing",
        )

        return {
            "enriched_chunks": enriched_chunks,
            "status": "labeled",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Labeling Error: {e}")

        IngestionTrackingService.update_job_status(
            job_id=state["job_id"],
            status="failed",
            error_stage="label",
            error_message=str(e),
            completed=True,
        )

        IngestionTrackingService.update_document_status(
            user_id=state["user_id"],
            document_id=state["document_id"],
            status="failed",
            last_job_id=state["job_id"],
        )

        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "label",
        }


async def store_node(state: IngestionState) -> IngestionState:
    """
    Step 3: Store enriched chunks in ChromaDB and Elasticsearch concurrently.
    """
    if state.get("status") == "failed":
        return state

    print(f"[3/3] Storing document_id: {state['document_id']}")

    try:
        chroma_task = EmbeddingService.embed_and_store(
            enriched_chunks=state["enriched_chunks"]
        )

        elastic_task = ElasticService.bulk_insert_chunks(
            enriched_chunks=state["enriched_chunks"]
        )

        chroma_count, elastic_count = await asyncio.gather(
            chroma_task,
            elastic_task,
        )

        print(f"Storage Complete: {chroma_count} vectors, {elastic_count} indexed docs.")

        IngestionTrackingService.update_job_status(
            job_id=state["job_id"],
            status="completed",
            chroma_count=chroma_count,
            elastic_count=elastic_count,
            completed=True,
        )

        IngestionTrackingService.update_document_status(
            user_id=state["user_id"],
            document_id=state["document_id"],
            status="indexed",
            last_job_id=state["job_id"],
            total_pages=len(state.get("pages", [])),
            total_chunks=len(state.get("enriched_chunks", [])),
        )

        return {
            "chroma_count": chroma_count,
            "elastic_count": elastic_count,
            "status": "completed",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Storage Error: {e}")

        IngestionTrackingService.update_job_status(
            job_id=state["job_id"],
            status="failed",
            error_stage="store",
            error_message=str(e),
            completed=True,
        )

        IngestionTrackingService.update_document_status(
            user_id=state["user_id"],
            document_id=state["document_id"],
            status="failed",
            last_job_id=state["job_id"],
        )

        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "store",
        }


workflow = StateGraph(IngestionState)

workflow.add_node("extract", extract_node)
workflow.add_node("label", label_node)
workflow.add_node("store", store_node)

workflow.add_edge(START, "extract")
workflow.add_edge("extract", "label")
workflow.add_edge("label", "store")
workflow.add_edge("store", END)

ingestion_app = workflow.compile()


# ==========================================
# SETUP TRACING & EXECUTE GRAPH
# ==========================================

# 1. Map your Pydantic settings to standard LangChain environment variables.
# (The LangChain SDK looks for LANGCHAIN_TRACING_V2 behind the scenes)
if settings.LANGSMITH_TRACING:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT


# 2. Example execution block
async def main():
    initial_state = {
        "file_path": "./data/sample_document.pdf",
        "user_id": "user_abc",
        "user_name": "Test User",
        "job_id": "job_xyz",
        "document_id": "doc_123"
    }
    
    print("Starting Coeus AI ingestion trace...")
    # Because tracing is enabled in os.environ, this single call handles the telemetry natively
    result = await ingestion_app.ainvoke(initial_state)
    print(f"Final Status: {result.get('status')}")

if __name__ == "__main__":
    asyncio.run(main())