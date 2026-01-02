from pydantic import BaseModel
from typing import List, Optional


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    document: str
    chunk_id: int


class QueryResponse(BaseModel):
    answer: str
    sources: List[Source]
