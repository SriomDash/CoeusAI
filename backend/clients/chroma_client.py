import logging
import chromadb
from chromadb.api import ClientAPI
from backend.config import settings

logger = logging.getLogger("coeus_ai.chroma_bus")

class ChromaBus:
    def __init__(self):
        self.client: ClientAPI | None = None

    async def connect(self):
        """
        Initializes the ChromaDB persistent client and verifies the storage path.
        """
        if self.client:
            return

        try:
            logger.info(f"Connecting to ChromaDB at {settings.CHROMA_PATH}...")
            
            # We wrap the sync call in a standard way so the Bus pattern remains consistent
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)
            
            # Verification: Heartbeat check to ensure the DB is responsive
            self.client.heartbeat()
            logger.info("ChromaDB Connected and Heartbeat verified.")

        except Exception as e:
            logger.error(f"ChromaDB Connection Failed: {e}")
            self.client = None
            raise e

    async def close(self):
        """
        Resets the client reference. PersistentClient handles file closing 
        internally, but clearing the reference prevents accidental post-shutdown leaks.
        """
        if self.client:
            logger.info("ChromaDB Connection Reference Cleared.")
            self.client = None

    def get_collection(self, name: str):
        """
        Returns or creates a collection.
        """
        if not self.client:
            raise RuntimeError("ChromaDB client is not initialized. Call connect() first.")
        return self.client.get_or_create_collection(name=name)

# Singleton Instance
chroma_bus = ChromaBus()