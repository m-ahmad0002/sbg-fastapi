from pydantic import BaseModel
from typing import List, Optional


class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Source(BaseModel):
    document: str
    chunk_id: int


class QueryResponse(BaseModel):
    session_id: str
    answer: str
    sources: Optional[List[str]] = []


# =========================
# NEW MODELS FOR AGENTS
# =========================

class AgentRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class NetworkAgentResponse(BaseModel):
    session_id: str
    guidance: str
    sources: Optional[List[str]] = []


class CriteriaAgentResponse(BaseModel):
    session_id: str
    evaluation: str
    sources: Optional[List[str]] = []
