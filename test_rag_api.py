#!/usr/bin/env python3
"""
Test script for RAG API: multiple users, each with multiple questions (session memory).
Run with: python test_rag_api.py [BASE_URL]
Default BASE_URL: http://localhost:8002
"""
import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://localhost:8002"
NUM_USERS = 10
QUESTIONS_PER_USER = 5


def request(method: str, path: str, body: dict = None) -> tuple[int, dict]:
    url = f"{BASE_URL.rstrip('/')}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        try:
            return e.code, json.loads(body)
        except json.JSONDecodeError:
            return e.code, {"detail": body}
    except urllib.error.URLError as e:
        print(f"Connection error: {e}")
        sys.exit(1)


def main():
    global BASE_URL
    if len(sys.argv) > 1:
        BASE_URL = sys.argv[1]
    print(f"Testing RAG API at {BASE_URL}")
    print(f"Users: {NUM_USERS}  |  Questions per user: {QUESTIONS_PER_USER}\n")

    # --- Health ---
    print("0. Health check")
    status, data = request("GET", "/health")
    if status != 200:
        print(f"   FAIL: {status} {data}")
        sys.exit(1)
    print(f"   OK: {data}\n")

    # Questions each user will ask (back-and-forth conversation)
    question_templates = [
        "What information is available in the documents?",
        "Can you summarize that in one sentence?",
        "What are the main topics you mentioned?",
        "Tell me more about the first topic.",
        "In one short sentence, what should I remember from this?",
    ]
    # Pad if we have more questions than templates
    while len(question_templates) < QUESTIONS_PER_USER:
        question_templates.append(question_templates[-1])

    all_session_ids = []
    failed = []

    for user_idx in range(NUM_USERS):
        user_name = f"user_{user_idx + 1}"
        session_id = None
        print(f"--- {user_name} (questions 1–{QUESTIONS_PER_USER}) ---")

        for q_idx in range(QUESTIONS_PER_USER):
            q = question_templates[q_idx]
            payload = {"query": q}
            if session_id is not None:
                payload["session_id"] = session_id

            status, data = request("POST", "/rag/query", payload)
            if status != 200:
                print(f"   FAIL Q{q_idx + 1}: status {status} -> {data.get('detail', data)}")
                failed.append((user_name, q_idx + 1, status, data))
                break

            if "session_id" not in data or "answer" not in data or "sources" not in data:
                print(f"   FAIL Q{q_idx + 1}: missing session_id/answer/sources")
                failed.append((user_name, q_idx + 1, None, data))
                break

            if not isinstance(data["sources"], list):
                print(f"   FAIL Q{q_idx + 1}: sources must be list")
                failed.append((user_name, q_idx + 1, None, data))
                break

            sid = data["session_id"]
            if session_id is not None and sid != session_id:
                print(f"   FAIL Q{q_idx + 1}: session_id changed ({session_id} -> {sid})")
                failed.append((user_name, q_idx + 1, None, data))
                break

            session_id = sid
            answer_preview = (data["answer"] or "")[:80].replace("\n", " ")
            print(f"   Q{q_idx + 1} OK | session_id: {sid[:8]}... | answer: {answer_preview}...")

        if session_id and user_idx + 1 <= len(all_session_ids) + len(failed):
            if not failed or failed[-1][0] != user_name:
                all_session_ids.append((user_name, session_id))
                print(f"   {user_name}: session_id = {session_id}\n")
        elif not failed or failed[-1][0] != user_name:
            print()

    # --- Summary ---
    print("=" * 50)
    if failed:
        print(f"FAILED: {len(failed)} request(s)")
        for u, q, st, d in failed:
            print(f"  {u} Q{q}: {st} {d}")
        sys.exit(1)

    assert len(all_session_ids) == NUM_USERS, f"Expected {NUM_USERS} users, got {len(all_session_ids)}"
    unique_sids = {s for _, s in all_session_ids}
    assert len(unique_sids) == NUM_USERS, "Session IDs must be unique per user"

    print("All checks passed.")
    print(f"  Users: {NUM_USERS}, questions per user: {QUESTIONS_PER_USER}")
    print(f"  Total requests: {NUM_USERS * QUESTIONS_PER_USER}")
    print("  Session IDs (one per user):")
    for name, sid in all_session_ids:
        print(f"    {name}: {sid}")

if __name__ == "__main__":
    main()
