from typing import Optional, List, Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# 1. Import traceable from LangSmith
from langsmith import traceable 

from backend.services.keyword_retriever import KeywordRetriever
from backend.services.semantic_retriever import SemanticRetriever


router = APIRouter(prefix="/api/v1/retrieve", tags=["Retrieval"])


# -----------------------------
# Request / Response Models
# -----------------------------

class RetrievalRequest(BaseModel):
    user_id: str = Field(..., description="Owner of the indexed chunks")
    query: str = Field(..., min_length=1, description="User question or search query")
    document_id: Optional[str] = Field(default=None, description="Optional document filter")
    source: Optional[str] = Field(default=None, description="Optional source/file filter")
    top_k: int = Field(default=10, ge=1, le=50, description="Number of results to return")


class RetrievalResult(BaseModel):
    chunk_id: str
    document_id: Optional[str] = None
    source: Optional[str] = None
    page: Optional[int] = None
    chunk_index: Optional[int] = None
    content: str
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    search_terms: Optional[List[str]] = None
    score: float
    retrieval_type: str


class RetrievalResponse(BaseModel):
    query: str
    user_id: str
    total_results: int
    results: List[RetrievalResult]


# -----------------------------
# Service Instances
# -----------------------------

keyword_retriever = KeywordRetriever()
semantic_retriever = SemanticRetriever()


# -----------------------------
# Health / Ping
# -----------------------------

@router.get("/health")
def retrieval_health():
    return {
        "message": "Retrieval router is working"
    }


# -----------------------------
# Keyword Retrieval
# -----------------------------

@router.post("/keyword", response_model=RetrievalResponse)
@traceable(name="API: Keyword Search", run_type="retriever") # 2. Add the decorator here
async def retrieve_keyword(payload: RetrievalRequest):
    try:
        results = await keyword_retriever.search(
            query=payload.query,
            user_id=payload.user_id,
            document_id=payload.document_id,
            source=payload.source,
            top_k=payload.top_k,
        )

        return RetrievalResponse(
            query=payload.query,
            user_id=payload.user_id,
            total_results=len(results),
            results=results,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Keyword retrieval failed: {str(e)}"
        )

# -----------------------------
# Semantic Retrieval
# -----------------------------

@router.post("/semantic", response_model=RetrievalResponse)
@traceable(name="API: Semantic Search", run_type="retriever") # 3. And add it here!
async def retrieve_semantic(payload: RetrievalRequest):
    try:
        results = await semantic_retriever.search(
            query=payload.query,
            user_id=payload.user_id,
            document_id=payload.document_id,
            source=payload.source,
            top_k=payload.top_k,
        )

        return RetrievalResponse(
            query=payload.query,
            user_id=payload.user_id,
            total_results=len(results),
            results=results,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Semantic retrieval failed: {str(e)}"
        )