import os
import torch
import chromadb
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
from backend.config import settings

class EmbeddingService:
    @staticmethod
    def _sanitize_collection_name(name: str) -> str:
        clean_name = "".join(c if c.isalnum() else "_" for c in name)
        return f"user_collection_{clean_name}"[:63]

    @staticmethod
    def get_collection(user_name: str):
        """
        Initializes ChromaDB with a LOCAL Embedding Function running on CUDA.
        """
        persist_path = "./chroma_db"
        os.makedirs(persist_path, exist_ok=True)

        client = chromadb.PersistentClient(path=persist_path)

        # Determine if CUDA is available
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Embedding Model Device: {device.upper()}")

        # Initialize Local Embedding Function
        local_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.HF_EMBEDDING_MODEL, 
            device=device
        )

        collection_name = EmbeddingService._sanitize_collection_name(user_name)

        return client.get_or_create_collection(
            name=collection_name,
            embedding_function=local_ef,
            metadata={"hnsw:space": "cosine"} 
        )

    @classmethod
    async def embed_and_store(cls, user_name: str, labeled_data: List[Dict[str, Any]]) -> int:
        if not labeled_data:
            print("No data to embed.")
            return 0

        collection = cls.get_collection(user_name)

        ids = []
        documents = []
        metadatas = []

        for i, item in enumerate(labeled_data):
            chunk_id = f"{item['job_id']}_chunk_{i}"
            documents.append(item['content'])
            
            raw_meta = item.get('metadata', {})
            flat_meta = {
                "user_id": str(item['user_id']),
                "job_id": str(item['job_id']),
                "summary": str(item.get('summary', '')),
                "keywords": ", ".join(raw_meta.get('keywords', [])),
                "search_terms": ", ".join(raw_meta.get('search_terms', []))
            }
            metadatas.append(flat_meta)
            ids.append(chunk_id)

        try:
            #If Existing Update, else Insert
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            print(f"Successfully locally embedded {len(ids)} chunks for user: {user_name}")
            return len(ids)
            
        except Exception as e:
            print(f"Local Embedding Failed: {e}")
            raise e