from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings

class GeminiClient:
    def __init__(self):
        
        self.model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            temperature=1.0,  
            max_tokens=None,
            timeout=None,
            max_retries=settings.DEBUG and 0 or 2,
            google_api_key=settings.GEMINI_API_KEY
        )

# Single instance for the application
gemini_bus = GeminiClient()