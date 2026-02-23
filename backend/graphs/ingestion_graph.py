import aiofiles
import asyncio
from typing import List, Dict, Any, Optional
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

# Import all services
from backend.services.pdf_service import PDFService
from backend.services.labeling_service import LabelingService
from backend.services.embedding_service import EmbeddingService
from backend.services.elastic_service import ElasticService

# 1. Define the State
class IngestionState(TypedDict):
    # Inputs
    file_path: str
    user_id: str
    user_name: str
    job_id: str
    
    # Internal Data
    raw_text: Optional[str]
    visuals: List[str]
    text_chunks: List[str]         
    labeled_data: List[Dict[str, Any]] 
    
    # Outputs
    chroma_count: int  
    elastic_count: int 
    status: str
    error: Optional[str]

# 2. Define the Nodes
async def extract_node(state: IngestionState) -> IngestionState:
    """
    Step 1: Reads PDF, extracts text, and creates chunks.
    """
    print(f"[1/3] Extracting: {state['file_path']}")
    try:
        # Read file asynchronously
        async with aiofiles.open(state['file_path'], 'rb') as f:
            content = await f.read()

        # Extract raw text
        text, visuals = PDFService.extract_text(state['file_path'], content)

        # Chunk text (Logic inside PDFService handles the splitting)
        docs = PDFService.chunk_text(
            text=text, 
            source=state['file_path'], 
            visuals=visuals,
            user_id=state['user_id'],
            job_id=state['job_id']
        )
        
        # We need plain strings for the Labeling Service
        text_chunks = [doc.page_content for doc in docs]

        return {
            "raw_text": text,
            "visuals": visuals,
            "text_chunks": text_chunks,
            "status": "extracted"
        }
    
    except Exception as e:
        print(f"Extraction Error: {e}")
        return {
            "error": str(e), 
            "status": "failed"
        }

async def label_node(state: IngestionState) -> IngestionState:
    """
    Step 2: Sends chunks to AI (Groq) to generate semantic metadata.
    """
    # Skip if previous step failed
    if state.get("status") == "failed":
        return state

    print(f"[2/3] Labeling {len(state['text_chunks'])} chunks...")
    try:
        labeled_data = await LabelingService.process_and_link(
            all_chunks=state['text_chunks'],
            user_id=state['user_id'],
            job_id=state['job_id']
        )
        
        return {
            "labeled_data": labeled_data,
            "status": "labeled"
        }
    except Exception as e:
        print(f"Labeling Error: {e}")
        return {
            "error": str(e), 
            "status": "failed"
        }

async def store_node(state: IngestionState) -> IngestionState:
    """
    Step 3: Stores data in ChromaDB (Vector) and Elasticsearch (Keyword) concurrently.
    """
    if state.get("status") == "failed":
        return state

    print(f"[3/3] Storing data for user: {state['user_name']}")
    try:
        # Define the two async tasks
        chroma_task = EmbeddingService.embed_and_store(
            user_name=state['user_name'],
            labeled_data=state['labeled_data']
        )
        
        elastic_task = ElasticService.bulk_insert_chunks(
            labeled_data=state['labeled_data']
        )

        # Execute them in parallel and wait for both to finish
        chroma_count, elastic_count = await asyncio.gather(chroma_task, elastic_task)
        
        print(f"Storage Complete: {chroma_count} vectors, {elastic_count} indexed docs.")
        
        return {
            "chroma_count": chroma_count,
            "elastic_count": elastic_count,
            "status": "completed"
        }
    except Exception as e:
        print(f"Storage Error: {e}")
        return {
                "error": str(e), 
                "status": "failed"
            }

# 3. Build the Graph
workflow = StateGraph(IngestionState)

# Add Nodes
workflow.add_node("extract", extract_node)
workflow.add_node("label", label_node)
workflow.add_node("store", store_node)


workflow.add_edge(START, "extract")
workflow.add_edge("extract", "label")
workflow.add_edge("label", "store")
workflow.add_edge("store", END)

# Compile into a Runnable Application
ingestion_app = workflow.compile()


