from __future__ import annotations
import hashlib
import io
import re
from typing import List, Dict, Any

import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable  # <-- 1. Import traceable

from backend.config import get_settings

cfg = get_settings()

class PDFServiceError(Exception):
    pass

class NoTextFoundError(PDFServiceError):
    pass

class PDFService:
    
    @staticmethod
    @traceable(name="PDFService: Generate Doc ID", run_type="tool") # <-- 2. Trace ID generation
    def generate_document_id(raw_bytes: bytes) -> str:
        """
        Generate a stable document ID from the PDF file contents.
        """
        return hashlib.sha256(raw_bytes).hexdigest()

    @staticmethod
    @traceable(name="PDFService: Extract Pages", run_type="tool") # <-- 3. Trace parsing speed
    def extract_pages(filename: str, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Extract text page by page from a PDF.
        
        Returns a list like:
        [
            {
                "page": 1,
                "text": "...",
                "source": "file.pdf"
            },
            ...
        ]
        """
        try:
            extracted_pages: List[Dict[str, Any]] = []

            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page_no, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()

                    if not text:
                        continue

                    clean_text = re.sub(r"\n{3,}", "\n\n", text).strip()

                    if not clean_text:
                        continue

                    extracted_pages.append(
                        {
                            "page": page_no,
                            "text": clean_text,
                            "source": filename,
                        }
                    )

            if not extracted_pages:
                raise NoTextFoundError("No selectable text found in this PDF.")

            return extracted_pages

        except NoTextFoundError:
            raise
        except Exception as exc:
            raise PDFServiceError(f"Extraction failed: {exc}") from exc

    @staticmethod
    @traceable(name="PDFService: Chunk Pages", run_type="tool") # <-- 4. Trace chunking
    def chunk_pages(
        pages: List[Dict[str, Any]],
        user_id: str,
        job_id: str,
        document_id: str,
    ) -> List[Dict[str, Any]]:
        """
        Chunk extracted pages while preserving metadata.

        Returns structured chunk records like:
        [
            {
                "id": "...",
                "content": "...",
                "source_metadata": {...}
            }
        ]
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=cfg.CHUNK_SIZE,
            chunk_overlap=cfg.CHUNK_OVERLAP,
            add_start_index=True,
            separators=["\n\n", "\n", ".", " ", ""],
        )

        chunk_records: List[Dict[str, Any]] = []
        global_chunk_index = 0

        for page_data in pages:
            page_doc = Document(
                page_content=page_data["text"],
                metadata={
                    "source": page_data["source"],
                    "page": page_data["page"],
                    "user_id": user_id,
                    "job_id": job_id,
                    "document_id": document_id,
                },
            )

            split_docs = splitter.split_documents([page_doc])

            for doc in split_docs:
                source_metadata = dict(doc.metadata)
                source_metadata["chunk_index"] = global_chunk_index

                chunk_records.append(
                    {
                        "id": f"{document_id}_chunk_{global_chunk_index}",
                        "content": doc.page_content,
                        "source_metadata": source_metadata,
                    }
                )

                global_chunk_index += 1

        return chunk_records

    @staticmethod
    @traceable(name="PDFService: Extract Raw Text", run_type="tool") # <-- 5. Trace text agg
    def extract_raw_text(pages: List[Dict[str, Any]]) -> str:
        """
        Combine page texts into one raw text string when needed.
        """
        return "\n\n".join(page["text"] for page in pages)