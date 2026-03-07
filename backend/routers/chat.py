from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.graphs.retrieval_graph import retrieval_app


router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])


class ChatRequest(BaseModel):
    user_id: str = Field(..., description="User ID owning the indexed documents")
    query: str = Field(..., min_length=1, description="User question")
    document_id: Optional[str] = Field(default=None, description="Optional document filter")
    source: Optional[str] = Field(default=None, description="Optional source/file filter")


class ChatResponse(BaseModel):
    query: str
    user_id: str
    status: str
    answer: Dict[str, Any]
    expanded_keywords: List[str]
    expanded_search_terms: List[str]
    intent_summary: str
    semantic_results: List[Dict[str, Any]]
    keyword_results: List[Dict[str, Any]]
    fused_results: List[Dict[str, Any]]
    reranked_results: List[Dict[str, Any]]
    error: Optional[str] = None
    error_stage: Optional[str] = None


@router.get("/health")
async def chat_health():
    return {"message": "Chat router is working"}


@router.post("/ask", response_model=ChatResponse)
async def ask_question(payload: ChatRequest):
    try:
        result = await retrieval_app.ainvoke({
            "query": payload.query,
            "user_id": payload.user_id,
            "document_id": payload.document_id,
            "source": payload.source,
        })

        return ChatResponse(
            query=payload.query,
            user_id=payload.user_id,
            status=result.get("status", "unknown"),
            answer=result.get("final_answer", {}),
            expanded_keywords=result.get("expanded_keywords", []),
            expanded_search_terms=result.get("expanded_search_terms", []),
            intent_summary=result.get("intent_summary", ""),
            semantic_results=result.get("semantic_results", []),
            keyword_results=result.get("keyword_results", []),
            fused_results=result.get("fused_results", []),
            reranked_results=result.get("reranked_results", []),
            error=result.get("error"),
            error_stage=result.get("error_stage"),
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Chat pipeline failed: {str(e)}"
        )