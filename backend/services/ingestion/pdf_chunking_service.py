from __future__ import annotations
import io
import re
from typing import List, Dict, Any

import pdfplumber
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langsmith import traceable

# UPDATED: Using our Bus Singleton
from backend.clients.supabase_client import supabase_bus
from backend.config import get_settings

cfg = get_settings()

class PDFServiceError(Exception): pass
class NoTextFoundError(PDFServiceError): pass
class InvalidJobStateError(PDFServiceError): pass
class JobNotFoundError(PDFServiceError): pass

class PDFService:
    @staticmethod
    @traceable(name="PDFService: Extract Pages", run_type="tool")
    def extract_pages(filename: str, raw_bytes: bytes) -> List[Dict[str, Any]]:
        try:
            extracted_pages: List[Dict[str, Any]] = []

            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                for page_no, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text()
                    if not text:
                        continue

                    # Clean up excessive newlines
                    clean_text = re.sub(r"\n{3,}", "\n\n", text).strip()

                    if not clean_text:
                        continue

                    extracted_pages.append({
                        "page": page_no,
                        "text": clean_text,
                        "source": filename,
                    })

            if not extracted_pages:
                raise NoTextFoundError("No selectable text found in this PDF.")

            return extracted_pages

        except NoTextFoundError:
            raise
        except Exception as exc:
            raise PDFServiceError(f"Extraction failed: {exc}") from exc

    @staticmethod
    @traceable(name="PDFService: Chunk Pages", run_type="tool")
    def chunk_pages(
        pages: List[Dict[str, Any]],
        user_id: str,
        job_id: str,
        document_id: str,
    ) -> List[Dict[str, Any]]:
        # High-performance recursive splitting for RAG
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

                chunk_records.append({
                    "id": f"{document_id}_chunk_{global_chunk_index}",
                    "content": doc.page_content,
                    "source_metadata": source_metadata,
                })

                global_chunk_index += 1

        return chunk_records

    @staticmethod
    async def _get_job(user_id: str, job_id: str) -> Dict[str, Any]:
        # UPDATED: Use the bus singleton
        supabase = supabase_bus.get_client()

        job_result = (
            await supabase.table("ingestion_jobs")
            .select("id, user_id, document_id, status")
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not job_result.data:
            raise JobNotFoundError(f"No job found for job_id={job_id}")

        return job_result.data[0]

    @staticmethod
    async def _get_document(user_id: str, document_id: str) -> Dict[str, Any]:
        # UPDATED: Use the bus singleton
        supabase = supabase_bus.get_client()

        document_result = (
            await supabase.table("documents")
            .select("id, user_id, file_name, storage_path")
            .eq("id", document_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not document_result.data:
            raise PDFServiceError(f"No document found for document_id={document_id}")

        return document_result.data[0]

    @staticmethod
    @traceable(name="PDFService: Run Extraction For Job", run_type="chain")
    async def run_pdf_extraction_for_job(user_id: str, job_id: str) -> Dict[str, Any]:
        # UPDATED: Use the bus singleton
        supabase = supabase_bus.get_client()
        job = await PDFService._get_job(user_id=user_id, job_id=job_id)

        if job["status"] != "uploaded":
            raise InvalidJobStateError(f"Job {job_id} is in status '{job['status']}'. Expected 'uploaded'.")

        try:
            document = await PDFService._get_document(user_id=user_id, document_id=job["document_id"])

            # Download bytes from Supabase Storage
            file_bytes = await supabase.storage.from_("raw_documents").download(document["storage_path"])

            pages = PDFService.extract_pages(filename=document["file_name"], raw_bytes=file_bytes)

            await supabase.table("ingestion_jobs").update({"status": "extracted"}).eq("id", job_id).execute()

            return {
                "user_id": user_id,
                "job_id": job_id,
                "document_id": document["id"],
                "status": "extracted",
                "page_count": len(pages),
                "pages": pages,
            }

        except Exception as exc:
            await supabase.table("ingestion_jobs").update({"status": "failed", "error_message": str(exc)}).eq("id", job_id).execute()
            raise

    @staticmethod
    @traceable(name="PDFService: Run Chunking For Job", run_type="chain")
    async def run_pdf_chunking_for_job(user_id: str, job_id: str) -> Dict[str, Any]:
        # UPDATED: Use the bus singleton
        supabase = supabase_bus.get_client()
        job = await PDFService._get_job(user_id=user_id, job_id=job_id)

        if job["status"] != "extracted":
            raise InvalidJobStateError(f"Job {job_id} is in status '{job['status']}'. Expected 'extracted'.")

        try:
            document = await PDFService._get_document(user_id=user_id, document_id=job["document_id"])
            file_bytes = await supabase.storage.from_("raw_documents").download(document["storage_path"])

            pages = PDFService.extract_pages(filename=document["file_name"], raw_bytes=file_bytes)

            chunk_records = PDFService.chunk_pages(
                pages=pages,
                user_id=user_id,
                job_id=job_id,
                document_id=document["id"],
            )

            await supabase.table("ingestion_jobs").update({"status": "chunked"}).eq("id", job_id).execute()

            return {
                "user_id": user_id,
                "job_id": job_id,
                "document_id": document["id"],
                "status": "chunked",
                "page_count": len(pages),
                "chunk_count": len(chunk_records),
                "chunks": chunk_records,
            }

        except Exception as exc:
            await supabase.table("ingestion_jobs").update({"status": "failed", "error_message": str(exc)}).eq("id", job_id).execute()
            raise