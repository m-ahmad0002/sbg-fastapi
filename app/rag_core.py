import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from azure.core.credentials import AzureKeyCredential
from openai import AzureOpenAI

# Load environment variables from .env file FIRST
load_dotenv()

# Now read environment variables
SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY")
INDEX_NAME = os.getenv("AZURE_SEARCH_INDEX_NAME", "rag-documents")

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_EMBED_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT")
AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

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
    response = openai_client.embeddings.create(
        model=AZURE_OPENAI_EMBED_DEPLOYMENT,
        input=text
    )
    return response.data[0].embedding


def retrieve_documents(query: str, top_k: int = 5):
    vector = generate_embedding(query)

    vector_query = VectorizedQuery(
        vector=vector,
        k_nearest_neighbors=top_k,
        fields="contentVector"
    )

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        select=["content", "filename", "chunk_id"],
        top=top_k
    )

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

    response = openai_client.chat.completions.create(
        model=AZURE_OPENAI_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0,
        max_tokens=800
    )

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
