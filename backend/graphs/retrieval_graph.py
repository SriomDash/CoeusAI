from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

from backend.services.query_expansion_service import QueryExpansionService
from backend.services.semantic_retriever import SemanticRetriever
from backend.services.keyword_retriever import KeywordRetriever
from backend.services.fusion_service import FusionService
from backend.services.reranker_service import RerankerService
from backend.services.answer_service import AnswerService


class RetrievalState(TypedDict, total=False):
    # Inputs
    query: str
    user_id: str
    document_id: Optional[str]
    source: Optional[str]

    # Query expansion
    expanded_keywords: List[str]
    expanded_search_terms: List[str]
    intent_summary: str

    # Retrieval outputs
    semantic_results: List[Dict[str, Any]]
    keyword_results: List[Dict[str, Any]]
    fused_results: List[Dict[str, Any]]
    reranked_results: List[Dict[str, Any]]

    # Final output
    final_answer: Dict[str, Any]

    # Status / error
    status: str
    error: Optional[str]
    error_stage: Optional[str]


semantic_retriever = SemanticRetriever()
keyword_retriever = KeywordRetriever()


async def expand_query_node(state: RetrievalState) -> RetrievalState:
    """
    Step 1: Expand query for lexical retrieval.
    Original query remains unchanged for semantic retrieval.
    """
    print(f"[1/5] Expanding query: {state['query']}")

    try:
        expansion = await QueryExpansionService.expand_query(state["query"])

        return {
            "expanded_keywords": expansion.keywords,
            "expanded_search_terms": expansion.search_terms,
            "intent_summary": expansion.intent_summary,
            "status": "expanded",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Query Expansion Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "expand_query",
        }


async def retrieve_node(state: RetrievalState) -> RetrievalState:
    """
    Step 2: Run semantic and keyword retrieval in parallel.
    """
    if state.get("status") == "failed":
        return state

    print(f"[2/5] Retrieving for user_id: {state['user_id']}")

    try:
        semantic_task = semantic_retriever.search(
            query=state["query"],
            user_id=state["user_id"],
            document_id=state.get("document_id"),
            source=state.get("source"),
            top_k=10,
        )

        keyword_task = keyword_retriever.search(
            query=state["query"],
            user_id=state["user_id"],
            document_id=state.get("document_id"),
            source=state.get("source"),
            top_k=10,
            expanded_keywords=state.get("expanded_keywords", []),
            expanded_search_terms=state.get("expanded_search_terms", []),
        )

        semantic_results, keyword_results = await __import__("asyncio").gather(
            semantic_task,
            keyword_task,
        )

        return {
            "semantic_results": semantic_results,
            "keyword_results": keyword_results,
            "status": "retrieved",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Retrieval Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "retrieve",
        }


async def fuse_node(state: RetrievalState) -> RetrievalState:
    """
    Step 3: Fuse semantic and keyword results using Reciprocal Rank Fusion.
    """
    if state.get("status") == "failed":
        return state

    print("[3/5] Fusing retrieval results...")

    try:
        fused_results = FusionService.reciprocal_rank_fusion(
            semantic_results=state.get("semantic_results", []),
            keyword_results=state.get("keyword_results", []),
            rrf_k=60,
            top_k=10,
        )

        return {
            "fused_results": fused_results,
            "status": "fused",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Fusion Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "fuse",
        }


async def rerank_node(state: RetrievalState) -> RetrievalState:
    """
    Step 4: Rerank fused candidates using Cohere.
    """
    if state.get("status") == "failed":
        return state

    print("[4/5] Reranking fused results...")

    try:
        reranked_results = RerankerService.rerank(
            query=state["query"],
            candidates=state.get("fused_results", []),
            top_k=5,
            use_summary=True,
        )

        return {
            "reranked_results": reranked_results,
            "status": "reranked",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Reranking Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "rerank",
        }


async def answer_node(state: RetrievalState) -> RetrievalState:
    """
    Step 5: Generate final grounded answer from top reranked chunks.
    """
    if state.get("status") == "failed":
        return state

    print("[5/5] Generating grounded answer...")

    try:
        final_answer = await AnswerService.generate_answer(
            query=state["query"],
            reranked_chunks=state.get("reranked_results", []),
            top_k=5,
        )

        return {
            "final_answer": final_answer,
            "status": "completed",
            "error": None,
            "error_stage": None,
        }

    except Exception as e:
        print(f"Answer Generation Error: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "error_stage": "answer",
        }


workflow = StateGraph(RetrievalState)

workflow.add_node("expand_query", expand_query_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("fuse", fuse_node)
workflow.add_node("rerank", rerank_node)
workflow.add_node("answer", answer_node)

workflow.add_edge(START, "expand_query")
workflow.add_edge("expand_query", "retrieve")
workflow.add_edge("retrieve", "fuse")
workflow.add_edge("fuse", "rerank")
workflow.add_edge("rerank", "answer")
workflow.add_edge("answer", END)

retrieval_app = workflow.compile()