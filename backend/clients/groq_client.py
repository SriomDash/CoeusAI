import instructor
from groq import AsyncGroq
from langchain_groq import ChatGroq

from backend.config import settings


class GroqClients:
    def __init__(self):
        self.langchain_model = ChatGroq(
            model=settings.GROQ_MODEL,
            temperature=0,
            max_tokens=8192,
            timeout=None,
            max_retries=2,
            api_key=settings.GROQ_API_KEY,
        )

        self.instructor_async_client = instructor.from_groq(
            AsyncGroq(api_key=settings.GROQ_API_KEY),
            mode=instructor.Mode.JSON,
        )


groq_clients = GroqClients()