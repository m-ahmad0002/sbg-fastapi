from fastapi import FastAPI, HTTPException
from app.models import QueryRequest, QueryResponse
from app.rag_core import answer_question
import logging
import json
import datetime

app = FastAPI(
    title="SBG RAG API",
    description="Azure AI Search powered RAG API for Copilot Studio",
    version="1.0.0"
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("audit_logger")


@app.post("/rag/query", response_model=QueryResponse)
def rag_query(request: QueryRequest):
    try:
        # Call RAG engine
        result = answer_question(request.query)

        # -------------------------------
        # AUDIT TRAIL LOG (F-006)
        # -------------------------------
        audit_log = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "session_id": request.session_id,
            "user_query": request.query,
            "ai_answer": result.get("answer"),
            "source_documents": result.get("sources"),
            "status": "SUCCESS"
        }

        logger.info("AUDIT_LOG: %s", json.dumps(audit_log))

        return result

    except Exception as e:
        # Failure audit log
        audit_log = {
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "session_id": request.session_id,
            "user_query": request.query,
            "error": str(e),
            "status": "ERROR"
        }

        logger.error("AUDIT_LOG: %s", json.dumps(audit_log))
        raise HTTPException(status_code=500, detail="Internal Server Error")
