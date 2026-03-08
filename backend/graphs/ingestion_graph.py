import asyncio
import os
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from backend.config import settings

from backend.services.ingestion.pdf_chunking_service import PDFService
from backend.services.ingestion.labeling_service import LabelingService
from backend.services.ingestion.embedding_service import EmbeddingService
from backend.services.ingestion.keyword_insertion_service import ElasticService
from backend.services.ingestion.ingestion_finalizer_service import IngestionFinalizerService


class IngestionState(TypedDict, total=False):
    user_id: str
    user_name: str
    job_id: str
    document_id: str

    pages: List[Dict[str, Any]]
    raw_text: Optional[str]
    chunk_records: List[Dict[str, Any]]
    enriched_chunks: List[Dict[str, Any]]

    chroma_count: int
    elastic_count: int

    status: str
    error: Optional[str]
    error_stage: Optional[str]


STATUS_TO_NODE = {
    "uploaded": "extract",
    "extracted": "chunk",
    "chunked": "label",
    "ai_labelled": "embed",
    "vectors_inserted": "keyword_insert",
    "keyword_inserted": "finalize",
}


def route_from_status(state: IngestionState) -> str:
    """
    Route graph entrypoint based on current job status.
    """
    status = state.get("status", "uploaded")

    if status not in STATUS_TO_NODE:
        return "extract"

    return STATUS_TO_NODE[status]


async def extract_node(state: IngestionState) -> IngestionState:
    """
    Step 1: Extract pages from uploaded PDF.
    Allowed only when job status = uploaded.
    Service updates job status to extracted.
    """
    print(f"[1/6] Extracting for job_id={state['job_id']}")

    try:
        result = await PDFService.run_pdf_extraction_for_job(
            user_id=state["user_id"],
            job_id=state["job_id"],
        )

        return {
            "document_id": result["document_id"],
            "pages": result["pages"],
            "raw_text": PDFService.extract_raw_text(result["pages"]),
            "status": result["status"],
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Extraction Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "extract",
        }


async def chunk_node(state: IngestionState) -> IngestionState:
    """
    Step 2: Chunk extracted PDF.
    Allowed only when job status = extracted.
    Service updates job status to chunked.
    """
    if state.get("status") == "failed":
        return state

    print(f"[2/6] Chunking for job_id={state['job_id']}")

    try:
        result = await PDFService.run_pdf_chunking_for_job(
            user_id=state["user_id"],
            job_id=state["job_id"],
        )

        return {
            "document_id": result["document_id"],
            "chunk_records": result["chunks"],
            "status": result["status"],
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Chunking Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "chunk",
        }


async def label_node(state: IngestionState) -> IngestionState:
    """
    Step 3: AI label chunks.
    Allowed only when job status = chunked.
    Service updates job status to ai_labelled.
    """
    if state.get("status") == "failed":
        return state

    print(f"[3/6] Labeling for job_id={state['job_id']}")

    try:
        chunk_records = state.get("chunk_records")

        # RESUME-SAFE: If RAM is wiped, pull from the "Filing Cabinet"
        if not chunk_records:
            # UPDATED: Use the singleton bus instead of a new connection
            from backend.clients.supabase_client import supabase_bus
            supabase = supabase_bus.get_client()

            result = (
                await supabase.table("document_chunks")
                .select("id, content, source_metadata")
                .eq("user_id", state["user_id"])
                .eq("job_id", state["job_id"])
                .order("chunk_index")
                .execute()
            )

            chunk_records = [
                {
                    "id": r["id"],
                    "content": r["content"],
                    "source_metadata": r["source_metadata"],
                }
                for r in result.data
            ]

        # Call the actual AI service to enrich the data
        enriched_chunks = await LabelingService.process_and_link(
            chunk_records=chunk_records,
            user_id=state["user_id"],
            job_id=state["job_id"],
        )

        return {
            "enriched_chunks": enriched_chunks,
            "status": "ai_labelled",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Labeling Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "label",
        }

async def embed_node(state: IngestionState) -> IngestionState:
    """
    Step 4: Embed chunks and insert vectors into Chroma.
    Allowed only when job status = ai_labelled.
    Service updates job status to embedded -> vectors_inserted.
    """
    if state.get("status") == "failed":
        return state

    print(f"[4/6] Embedding for job_id={state['job_id']}")

    try:
        chroma_count = await EmbeddingService.embed_and_store(
            enriched_chunks=state["enriched_chunks"],
            user_id=state["user_id"],
            job_id=state["job_id"],
        )

        return {
            "chroma_count": chroma_count,
            "status": "vectors_inserted",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Embedding Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "embed",
        }


async def keyword_insert_node(state: IngestionState) -> IngestionState:
    """
    Step 5: Insert keyword documents into Elasticsearch.
    Allowed only when job status = vectors_inserted.
    Service updates job status to keyword_inserted.
    """
    if state.get("status") == "failed":
        return state

    print(f"[5/6] Keyword insertion for job_id={state['job_id']}")

    try:
        elastic_count = await ElasticService.bulk_insert_chunks(
            enriched_chunks=state["enriched_chunks"],
            user_id=state["user_id"],
            job_id=state["job_id"],
        )

        return {
            "elastic_count": elastic_count,
            "status": "keyword_inserted",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Keyword Insertion Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "keyword_insert",
        }


async def finalize_node(state: IngestionState) -> IngestionState:
    """
    Final step: mark ingestion job as done.
    Allowed only when job status = keyword_inserted.
    """
    if state.get("status") == "failed":
        return state

    print(f"[6/6] Finalizing job_id={state['job_id']}")

    try:
        result = await IngestionFinalizerService.finalize_job(
            user_id=state["user_id"],
            job_id=state["job_id"],
        )

        return {
            "document_id": result["document_id"],
            "status": result["status"],
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Finalization Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "finalize",
        }


workflow = StateGraph(IngestionState)

workflow.add_node("extract", extract_node)
workflow.add_node("chunk", chunk_node)
workflow.add_node("label", label_node)
workflow.add_node("embed", embed_node)
workflow.add_node("keyword_insert", keyword_insert_node)
workflow.add_node("finalize", finalize_node)

workflow.add_conditional_edges(
    START,
    route_from_status,
    {
        "extract": "extract",
        "chunk": "chunk",
        "label": "label",
        "embed": "embed",
        "keyword_insert": "keyword_insert",
        "finalize": "finalize",
    }
)

workflow.add_edge("extract", "chunk")
workflow.add_edge("chunk", "label")
workflow.add_edge("label", "embed")
workflow.add_edge("embed", "keyword_insert")
workflow.add_edge("keyword_insert", "finalize")
workflow.add_edge("finalize", END)

ingestion_app = workflow.compile()


if settings.LANGSMITH_TRACING:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT


async def main():
    initial_state = {
        "user_id": "user_abc",
        "user_name": "Test User",
        "job_id": "job_xyz",
        "document_id": "doc_123",
        "status": "uploaded",
    }

    print("Starting Coeus AI ingestion trace...")

    result = await ingestion_app.ainvoke(
        initial_state,
        config={
            "run_name": f"ingestion_job_{initial_state['job_id']}",
            "tags": [
                "ingestion",
                "rag",
                f"user:{initial_state['user_id']}",
                f"job:{initial_state['job_id']}",
            ],
            "metadata": {
                "job_id": initial_state["job_id"],
                "user_id": initial_state["user_id"],
                "user_name": initial_state.get("user_name"),
                "document_id": initial_state.get("document_id"),
                "thread_id": initial_state["job_id"],
                "pipeline": "rag_ingestion",
            },
            "configurable": {
                "thread_id": initial_state["job_id"],
            },
        },
    )

    print(f"Final Status: {result.get('status')}")


if __name__ == "__main__":
    asyncio.run(main())