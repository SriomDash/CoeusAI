import logging
from elasticsearch import AsyncElasticsearch
from backend.config import settings

logger = logging.getLogger("coeus_ai.elastic_bus")

class ElasticBus:
    def __init__(self):
        self.client: AsyncElasticsearch | None = None

    async def connect(self):
        """
        Initializes the Elasticsearch client based on configuration (Cloud or Local).
        """
        if self.client:
            return  # Already connected

        try:
            logger.info("Connecting to Elasticsearch...")
            
            # 1. Cloud Configuration (API Key)
            if settings.ELASTIC_SEARCH_API_KEY:
                self.client = AsyncElasticsearch(
                    hosts=settings.ELASTIC_SEARCH_URL,
                    api_key=settings.ELASTIC_SEARCH_API_KEY,
                    verify_certs=True
                )
            
            # 3. No Auth (Dev/Local)
            else:
                self.client = AsyncElasticsearch(settings.ELASTIC_SEARCH_URL)

            # Validate Connection
            if await self.client.ping():
                logger.info("Elasticsearch Connected Successfully.")
            else:
                logger.warning("Elasticsearch Connected, but Ping Failed.")

        except Exception as e:
            logger.error(f"Elasticsearch Connection Failed: {e}")
            raise e

    async def close(self):
        """
        Closes the client connection gracefully.
        """
        if self.client:
            await self.client.close()
            logger.info("Elasticsearch Connection Closed.")
            self.client = None

    def get_client(self) -> AsyncElasticsearch:
        """
        Returns the active client. Raises error if not initialized.
        """
        if not self.client:
            raise RuntimeError("Elasticsearch client is not initialized. Call connect() first.")
        return self.client

# Singleton Instance
elastic_bus = ElasticBus()