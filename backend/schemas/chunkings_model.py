from pydantic import BaseModel, Field
from typing import List

class ChunkMetadata(BaseModel):
    keywords: List[str] = Field(description="Specific technical terms, entities, or important nouns found in the text.")
    search_terms: List[str] = Field(description="3-5 likely queries or questions a user might type to find this content.")
    one_line_summary: str = Field(description="A concise summary of the chunk in one sentence.")

class BatchMetadata(BaseModel):
    metadata_list: List[ChunkMetadata]