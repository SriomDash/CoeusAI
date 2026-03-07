import os
import re
import torch
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any

# 1. Import traceable from LangSmith
from langsmith import traceable

from backend.config import settings


class EmbeddingService:
    @staticmethod
    def _sanitize_collection_name(user_id: str) -> str:
        """
        Build a safe Chroma collection name from user_id.
        """
        clean_name = "".join(c if c.isalnum() else "_" for c in str(user_id))
        return f"user_collection_{clean_name}"[:63]

    @staticmethod
    @traceable(name="Chroma: Get or Create Collection", run_type="tool") # 2. Trace DB initialization
    def get_collection(user_id: str):
        """
        Initialize ChromaDB persistent client and return the user's collection.
        Each user gets one collection.
        """
        persist_path = "./chroma_db"
        os.makedirs(persist_path, exist_ok=True)

        client = chromadb.PersistentClient(path=persist_path)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Embedding Model Device: {device.upper()}")

        local_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.HF_EMBEDDING_MODEL,
            device=device,
        )

        collection_name = EmbeddingService._sanitize_collection_name(user_id)

        return client.get_or_create_collection(
            name=collection_name,
            embedding_function=local_ef,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Light cleanup before embedding.
        """
        if not text:
            return ""

        text = re.sub(r"https?://\S+", "", text)
        text = text.replace("\u200b", " ")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        return text.strip()

    @staticmethod
    def _build_chroma_metadata(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Flatten enriched chunk structure into Chroma-safe metadata.
        """
        source_meta = item.get("source_metadata", {})
        ai_meta = item.get("ai_metadata", {})

        source_value = str(source_meta.get("source", ""))

        return {
            "user_id": str(item.get("user_id", "")),
            "job_id": str(item.get("job_id", "")),
            "document_id": str(item.get("document_id", "")),
            "source": source_value,
            "source_name": os.path.basename(source_value) if source_value else "",
            "page": int(source_meta.get("page", 0)),
            "chunk_index": int(source_meta.get("chunk_index", 0)),
            "summary": str(item.get("summary", "")),
            "keywords": ", ".join(ai_meta.get("keywords", [])),
            "search_terms": ", ".join(ai_meta.get("search_terms", [])),
        }

    @staticmethod
    def _build_semantic_document(item: Dict[str, Any]) -> str:
        """
        Build the text that will actually be embedded in Chroma.

        This is more effective than embedding raw content alone because it includes:
        - summary
        - keywords
        - search_terms
        - cleaned chunk content
        """
        ai_meta = item.get("ai_metadata", {})

        content = EmbeddingService._clean_text(item.get("content", "") or "")
        summary = EmbeddingService._clean_text(item.get("summary", "") or "")
        keywords = ", ".join(ai_meta.get("keywords", []))
        search_terms = ", ".join(ai_meta.get("search_terms", []))

        parts = []

        if summary:
            parts.append(f"Summary: {summary}")

        if keywords:
            parts.append(f"Keywords: {keywords}")

        if search_terms:
            parts.append(f"Search Terms: {search_terms}")

        if content:
            parts.append(f"Content: {content}")

        return "\n".join(parts).strip()

    @classmethod
    @traceable(name="Chroma: Embed and Upsert", run_type="tool") # 3. Trace the actual embedding process
    async def embed_and_store(
        cls,
        enriched_chunks: List[Dict[str, Any]],
    ) -> int:
        """
        Embed and upsert chunks into the user's Chroma collection.

        Behavior:
        - one collection per user_id
        - one stable chunk id per document chunk
        - same document re-upload updates existing vectors
        """
        if not enriched_chunks:
            print("No data to embed.")
            return 0

        user_id = str(enriched_chunks[0]["user_id"])
        collection = cls.get_collection(user_id)

        ids: List[str] = []
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for item in enriched_chunks:
            chunk_id = item["id"]
            semantic_document = cls._build_semantic_document(item)

            if not semantic_document:
                continue

            ids.append(chunk_id)
            documents.append(semantic_document)
            metadatas.append(cls._build_chroma_metadata(item))

        if not ids:
            print("No valid chunk content found for embedding.")
            return 0

        try:
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )
            print(
                f"Successfully embedded/upserted {len(ids)} chunks "
                f"for user_id: {user_id}"
            )
            return len(ids)

        except Exception as e:
            print(f"Local Embedding Failed: {e}")
            raise