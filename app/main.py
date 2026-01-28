from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.models import QueryRequest, QueryResponse
from app.rag_core import answer_question
import logging
import json
import datetime
import os

app = FastAPI(
    title="SBG RAG API",
    description="Azure AI Search powered RAG API for Copilot Studio",
    version="1.0.0"
)

# Enable CORS for Copilot Studio
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("audit_logger")

@app.get("/")
def root():
    """Health check endpoint"""
    return {
        "status": "running",
        "service": "SBG RAG API",
        "version": "1.0.0"
    }

@app.get("/health")
def health_check():
    """Health check for Azure App Service"""
    return {"status": "healthy"}

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
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# For local development
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)