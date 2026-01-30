import os
from urllib.parse import urlparse
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Load environment variables from .env file FIRST
load_dotenv()

# Now read environment variables (strip whitespace - trailing space causes 404)
def _getenv(key: str, default: str = None) -> str:
    val = os.getenv(key) or default
    return val.strip() if val else val

SEARCH_ENDPOINT = _getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_API_KEY = _getenv("AZURE_SEARCH_API_KEY")
INDEX_NAME = _getenv("AZURE_SEARCH_INDEX_NAME", "rag-documents")

AZURE_OPENAI_ENDPOINT = _getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = _getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_EMBED_DEPLOYMENT = _getenv("AZURE_OPENAI_EMBED_DEPLOYMENT")
AZURE_OPENAI_CHAT_DEPLOYMENT = _getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
# Use a supported data-plane API version (2025-04-14 causes "API version not supported" for embeddings)
AZURE_OPENAI_API_VERSION = _getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")

# OpenAI SDK requires the classic Azure OpenAI endpoint (openai.azure.com).
# Foundry URL (services.ai.azure.com) is converted to classic; if you get 404 on server,
# set AZURE_OPENAI_ENDPOINT in App Service to the classic URL directly, e.g.:
#   https://<your-resource-name>.openai.azure.com
if AZURE_OPENAI_ENDPOINT and "services.ai.azure.com" in AZURE_OPENAI_ENDPOINT:
    parsed = urlparse(AZURE_OPENAI_ENDPOINT)
    resource_name = parsed.netloc.split(".")[0]
    AZURE_OPENAI_ENDPOINT = f"https://{resource_name}.openai.azure.com"
    if AZURE_OPENAI_API_VERSION and AZURE_OPENAI_API_VERSION >= "2025-01-01":
        AZURE_OPENAI_API_VERSION = "2024-08-01-preview"

# Validate required environment variables
if not SEARCH_ENDPOINT:
    raise ValueError("AZURE_SEARCH_ENDPOINT environment variable is not set")
if not SEARCH_API_KEY:
    raise ValueError("AZURE_SEARCH_API_KEY environment variable is not set")
if not AZURE_OPENAI_ENDPOINT:
    raise ValueError("AZURE_OPENAI_ENDPOINT environment variable is not set")
if not AZURE_OPENAI_API_KEY:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set")
if not AZURE_OPENAI_EMBED_DEPLOYMENT:
    raise ValueError("AZURE_OPENAI_EMBED_DEPLOYMENT environment variable is not set")
if not AZURE_OPENAI_CHAT_DEPLOYMENT:
    raise ValueError("AZURE_OPENAI_CHAT_DEPLOYMENT environment variable is not set")

credential = AzureKeyCredential(SEARCH_API_KEY)

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=INDEX_NAME,
    credential=credential
)

openai_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION
)


def generate_embedding(text: str):
    try:
        response = openai_client.embeddings.create(
            model=AZURE_OPENAI_EMBED_DEPLOYMENT,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise RuntimeError(f"OpenAI Embeddings (404=wrong endpoint/deployment name): {e}") from e


def retrieve_documents(query: str, top_k: int = 5):
    vector = generate_embedding(query)

    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=top_k,
        fields="contentVector"
    )

    try:
        results = search_client.search(
            search_text=query,
            vector_queries=[vector_query],
            select=["content", "filename", "chunk_id"],
            top=top_k
        )
    except Exception as e:
        raise RuntimeError(f"Azure Search (404=wrong index/endpoint): {e}") from e

    documents = []
    for r in results:
        documents.append({
            "content": r["content"],
            "filename": r["filename"],
            "chunk_id": r["chunk_id"],
            "score": r["@search.score"]
        })

    return documents


def answer_question(question: str):
    docs = retrieve_documents(question)

    if not docs:
        return {
            "answer": "I cannot find this information in the available documents.",
            "sources": []
        }

    context = "\n\n".join(
        f"[{d['filename']} – chunk {d['chunk_id']}]\n{d['content']}"
        for d in docs
    )

    system_prompt = (
        "You are a compliance-safe assistant. "
        "Answer strictly using the provided context. "
        "If the answer is not present, say so."
    )

    user_prompt = f"""
Context:
{context}

Question:
{question}
"""

    try:
        response = openai_client.chat.completions.create(
            model=AZURE_OPENAI_CHAT_DEPLOYMENT,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0,
            max_tokens=800
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI Chat (404=wrong endpoint/deployment name): {e}") from e

    answer = response.choices[0].message.content

    sources = [
        {
            "document": d["filename"],
            "chunk_id": d["chunk_id"]
        }
        for d in docs
    ]

    return {
        "answer": answer,
        "sources": sources
    }
