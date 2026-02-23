from __future__ import annotations
import io
import re
import pdfplumber
from typing import List
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from backend.config import get_settings

# Load settings
cfg = get_settings()

# Domain errors for better API mapping
class PDFServiceError(Exception): pass
class NoTextFoundError(PDFServiceError): pass

_IMG_PATTERN = re.compile(r'!\[.*?\]\(.*?\)')

class PDFService:
    @staticmethod
    def extract_text(filename: str, raw_bytes: bytes) -> tuple[str, list[str]]:
        """Extracts clean text and image markers from PDF bytes."""
        try:
            # Using io.BytesIO to treat raw bytes like a file object
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                pages = [page.extract_text() for page in pdf.pages if page.extract_text()]
            raw = " ".join(pages)
        except Exception as exc:
            raise PDFServiceError(f"Extraction failed: {exc}")

        visuals = _IMG_PATTERN.findall(raw)
        clean = _IMG_PATTERN.sub("", raw)
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

        if not clean:
            raise NoTextFoundError("No selectable text found in this PDF.")
        return clean, visuals

    @staticmethod
    def chunk_text(
        text: str, 
        source: str, 
        visuals: list[str], 
        user_id: str, 
        job_id: str
    ) -> List[Document]:
        """
        Splits text into overlapping LangChain Documents with user and job tracking.
        """
        # Wrap the raw string into a LangChain Document.
        doc = Document(
            page_content=text,
            metadata={
                "source": source, 
                "visuals": str(visuals),
                "user_id": user_id,
                "job_id": job_id
            }
        )
        
       #Split the document into chunks using RecursiveCharacterTextSplitter 
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.CHUNK_SIZE,       
            chunk_overlap=cfg.CHUNK_OVERLAP, 
            add_start_index=True,
            separators=["\n\n", "\n", ".", " ", ""]
        )
        
        return splitter.split_documents([doc])