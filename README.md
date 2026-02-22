# PDF RAG Scout

Full-stack RAG app — LangGraph backend (FastAPI) + streaming WebSocket frontend.

---

## Project Structure

```
.
├── requirements.txt
├── backend/
│   ├── main.py                    ← FastAPI app
│   ├── config.py                  ← All tuning knobs / env vars
│   ├── state_store.py             ← Global singleton (chunks, ChromaDB, BM25)
│   ├── services/
│   │   ├── pdf_service.py         ← Text extraction + chunking
│   │   ├── embedding_service.py   ← ChromaDB init, self-query LLM, upsert
│   │   ├── retrieval_service.py   ← BM25, vector search, RRF, HyDE/multi-query
│   │   ├── reranking_service.py   ← Cohere rerank (BM25-order fallback)
│   │   └── llm_service.py         ← Gemini 1.5 Flash streaming
│   ├── graphs/
│   │   ├── ingestion_graph.py     ← LangGraph: extract→chunk→self_query→index
│   │   └── query_graph.py         ← LangGraph: hyde→hybrid→rrf→rerank→generate
│   └── routers/
│       ├── pdf_router.py          ← POST /pdf/upload
│       └── query_router.py        ← WS /query/ws
└── frontend/
    └── index.html                 ← Zero-build UI
```

---

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. .env
GROQ_API_KEY=...
GROQ_MODEL=llama3-8b-8192
COHERE_API_KEY=...
GOOGLE_API_KEY=...

# 3. Run
uvicorn backend.main:app --reload --port 8000

# 4. Open frontend/index.html in browser
```

---

## Ingestion Pipeline  (LangGraph)
```
PDF bytes → extract_text → chunk_text → self_query_batch (LLM ×5 chunks)
          → upsert_chunks (ChromaDB + metadata) + BM25Retriever
```

## Query Pipeline  (LangGraph)
```
Question → generate_hyde_queries (HyDE + 3 variations)
         → hybrid_retrieval (vector×10 + BM25×10, per sub-query)
         → reciprocal_rank_fusion → top 10
         → Cohere rerank → top 5
         → Gemini 1.5 Flash stream
         → frontend: answer tokens + highlighted chunk cards
```

## Tuning knobs (config.py)
| Key | Default |
|-----|---------|
| chunk_size | 1024 |
| chunk_overlap | 256 |
| vector_top_k | 10 |
| bm25_top_k | 10 |
| rrf_top_n | 10 |
| rerank_top_n | 5 |
| num_sub_queries | 3 |