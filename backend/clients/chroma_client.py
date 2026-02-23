import chromadb
from backend.config import settings

class ChromaClient:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./chroma_db")
    
    def get_collection(self, name: str):
        return self.client.get_or_create_collection(name=name)

chroma_bus = ChromaClient()