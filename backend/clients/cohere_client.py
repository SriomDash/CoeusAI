import cohere
from backend.config import settings

class CohereClient:
    def __init__(self):
        self.client = cohere.Client(api_key=settings.CO_API_KEY)

co_bus = CohereClient()