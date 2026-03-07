from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings

class GeminiClient:
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=0.2,
            max_tokens=None,
            timeout=None,
            max_retries=settings.DEBUG and 0 or 2,
            google_api_key=settings.GEMINI_API_KEY
        )

gemini_bus = GeminiClient()