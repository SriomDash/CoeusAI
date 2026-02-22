from langchain_groq import ChatGroq
from backend.config import settings

class GroqClient:
    def __init__(self):
        self.model = ChatGroq(
            model=settings.GROQ_MODEL,
            temperature=0, 
            max_tokens=None,
            timeout=None,
            max_retries=2,
            api_key=settings.GROQ_API_KEY
        )

# Single instance for the application
groq_bus = GroqClient()