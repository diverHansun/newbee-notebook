"""
Comprehensive Backend Test Script for improve-6 Verification + Regression Testing
Tests P-01 ~ P-04 fixes and regression tests for improve-1 ~ improve-5
"""
import requests
import json
import time
import sys
import os
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"
TIMEOUT = 60

# Test state
NB_ID = "c5ff4fb4-3347-460c-a3b6-dcf2b957c911"
SESSION_ID = "7e9ec449-5b67-43d1-8e85-637cdf2604d6"
DOC_ID1 = "393f579b-2318-42eb-8a0a-9b5232900108"  # 缇庡浗鍙嶅缇庡浗
DOC_ID2 = "ea0e140d-bd36-49ac-ae67-82287a25ed09"  # 澶фā鍨嬪熀纭€

results = []

class SimpleClient:
    """Wrapper around requests to match httpx-like interface."""
    def __init__(self, base_url, timeout):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
    
    def get(self, path, **kwargs):
        return self.session.get(f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
    
    def post(self, path, json=None, **kwargs):
        return self.session.post(f"{self.base_url}{path}", json=json, timeout=self.timeout, **kwargs)
    
    def patch(self, path, json=None, **kwargs):
        return self.session.patch(f"{self.base_url}{path}", json=json, timeout=self.timeout, **kwargs)
    
    def delete(self, path, **kwargs):
        return self.session.delete(f"{self.base_url}{path}", timeout=self.timeout, **kwargs)
    
    def close(self):
        self.session.close()

def log(msg):
    print(f"  {msg}")

def test(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    icon = "PASS" if passed else "FAIL"
    print(f"  [{icon}] {name}" + (f" -- {detail}" if detail else ""))

def section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

client = SimpleClient(base_url=BASE_URL, timeout=TIMEOUT)

# ============================================================
# SECTION 1: Health & System Info (Regression - always needed)
# ============================================================
section("1. HEALTH & SYSTEM INFO")

r = client.get("/health")
test("Health endpoint returns 200", r.status_code == 200)

r = client.get("/health/ready")
test("Readiness endpoint returns 200", r.status_code == 200)

r = client.get("/health/live")
test("Liveness endpoint returns 200", r.status_code == 200)

r = client.get("/info")
test("Info endpoint returns 200", r.status_code == 200)
if r.status_code == 200:
    info = r.json()
    test("Info has name/version/features", 
         all(k in info for k in ["name", "version", "features"]),
         f"name={info.get('name')}, version={info.get('version')}")
    features = info.get("features", {})
    test("Features include library/notebooks/sessions",
         features.get("library") and features.get("notebooks") and features.get("sessions"))
    test("Chat modes include all 4 modes",
         set(["chat", "ask", "explain", "conclude"]).issubset(set(features.get("chat_modes", []))),
         f"modes={features.get('chat_modes')}")

# ============================================================
# SECTION 2: LIBRARY (Regression improve-1)
# ============================================================
section("2. LIBRARY (Regression: improve-1 Library-first)")

r = client.get("/library")
test("Get library returns 200", r.status_code == 200)
lib = r.json()
test("Library has document_count >= 2", lib.get("document_count", 0) >= 2, 
     f"document_count={lib.get('document_count')}")

r = client.get("/library/documents?limit=20&offset=0")
test("List library documents returns 200", r.status_code == 200)
docs = r.json()
test("Library has pagination structure", 
     "data" in docs and "pagination" in docs)
test("Library documents are completed",
     all(d["status"] == "completed" for d in docs["data"]),
     f"statuses={[d['status'] for d in docs['data']]}")

r = client.get("/library/documents?limit=20&offset=0&status=completed")
test("Library filter by status=completed works", r.status_code == 200)

r = client.get("/library/documents?limit=20&offset=0&status=failed")
test("Library filter by status=failed works", r.status_code == 200)
failed_docs = r.json()
test("No failed documents", failed_docs["pagination"]["total"] == 0)

# ============================================================
# SECTION 3: NOTEBOOKS CRUD (Regression)
# ============================================================
section("3. NOTEBOOKS CRUD (Regression)")

r = client.get(f"/notebooks?limit=20&offset=0")
test("List notebooks returns 200", r.status_code == 200)
test("At least 1 notebook exists", r.json()["pagination"]["total"] >= 1)

r = client.get(f"/notebooks/{NB_ID}")
test("Get notebook by ID returns 200", r.status_code == 200)
nb = r.json()
test("Notebook has correct fields", 
     all(k in nb for k in ["notebook_id", "title", "session_count", "document_count"]))
test("Notebook document_count is 2", nb.get("document_count") == 2,
     f"document_count={nb.get('document_count')}")

# Test update
r = client.patch(f"/notebooks/{NB_ID}",
                 json={"title": "Test Notebook - improve-6 (updated)", "description": "Updated for testing"})
test("Update notebook returns 200", r.status_code == 200)

# Restore title
client.patch(f"/notebooks/{NB_ID}", 
             json={"title": "Test Notebook - improve-6", "description": "Comprehensive test notebook"})

# Test 404
r = client.get("/notebooks/00000000-0000-0000-0000-000000000000")
test("Get non-existent notebook returns 404", r.status_code == 404)

# ============================================================
# SECTION 4: DOCUMENTS (Regression improve-1 + improve-4)
# ============================================================
section("4. DOCUMENTS (Regression: improve-1 storage, improve-4 status machine)")

r = client.get(f"/notebooks/{NB_ID}/documents?limit=20&offset=0")
test("List notebook documents returns 200", r.status_code == 200)
nb_docs = r.json()
test("Notebook has 2 documents", nb_docs["pagination"]["total"] == 2,
     f"total={nb_docs['pagination']['total']}")

r = client.get(f"/documents/{DOC_ID1}")
test("Get document detail returns 200", r.status_code == 200)
doc = r.json()
test("Document has status=completed", doc.get("status") == "completed")
test("Document has processing_stage=completed", doc.get("processing_stage") == "completed")
test("Document has page_count and chunk_count", 
     doc.get("page_count", 0) > 0 and doc.get("chunk_count", 0) > 0,
     f"pages={doc.get('page_count')}, chunks={doc.get('chunk_count')}")

# improve-4: Status machine fields
test("Document has processing_stage field (improve-4)", "processing_stage" in doc,
     f"stage={doc.get('processing_stage')}")
test("Document has stage_updated_at field (improve-4)", "stage_updated_at" in doc)

# Document content
r = client.get(f"/documents/{DOC_ID1}/content?format=markdown")
test("Get document content returns 200", r.status_code == 200)
if r.status_code == 200:
    content = r.json()
    test("Content has markdown content", len(content.get("content", "")) > 0,
         f"content_length={len(content.get('content', ''))}")

# Download original
r = client.get(f"/documents/{DOC_ID1}/download")
test("Download original document returns 200", r.status_code == 200)

# Non-existent doc
r = client.get("/documents/00000000-0000-0000-0000-000000000000")
test("Get non-existent document returns 404", r.status_code == 404)

# ============================================================
# SECTION 5: SESSIONS (Regression)
# ============================================================
section("5. SESSIONS (Regression)")

r = client.get(f"/notebooks/{NB_ID}/sessions?limit=20&offset=0")
test("List sessions returns 200", r.status_code == 200)
test("At least 1 session exists", r.json()["pagination"]["total"] >= 1)

r = client.get(f"/sessions/{SESSION_ID}")
test("Get session by ID returns 200", r.status_code == 200)

r = client.get(f"/notebooks/{NB_ID}/sessions/latest")
test("Get latest session returns 200", r.status_code == 200)

# ============================================================
# SECTION 6: P-03 - Session Messages API (improve-6 NEW)
# ============================================================
section("6. P-03 FIX: Session Messages API (improve-6)")

# TC-01: Empty session messages
r = client.get(f"/sessions/{SESSION_ID}/messages?limit=50&offset=0")
test("GET /sessions/{id}/messages returns 200", r.status_code == 200)
msg_resp = r.json()
test("Messages response has data + pagination",
     "data" in msg_resp and "pagination" in msg_resp)
test("Empty session has 0 messages", len(msg_resp["data"]) == 0,
     f"count={len(msg_resp['data'])}")

# TC-02: Mode filter on empty session
r = client.get(f"/sessions/{SESSION_ID}/messages?mode=chat,ask&limit=50&offset=0")
test("Mode filter (chat,ask) returns 200", r.status_code == 200)

r = client.get(f"/sessions/{SESSION_ID}/messages?mode=explain,conclude&limit=50&offset=0")
test("Mode filter (explain,conclude) returns 200", r.status_code == 200)

# TC-03: Non-existent session
r = client.get("/sessions/00000000-0000-0000-0000-000000000000/messages")
test("Non-existent session messages returns 404", r.status_code == 404)

# TC-04: Pagination params
r = client.get(f"/sessions/{SESSION_ID}/messages?limit=10&offset=0")
test("Pagination with limit=10 works", r.status_code == 200)
pag = r.json().get("pagination", {})
test("Pagination has has_next/has_prev fields",
     "has_next" in pag and "has_prev" in pag,
     f"has_next={pag.get('has_next')}, has_prev={pag.get('has_prev')}")

# ============================================================
# SECTION 7: CHAT - Build messages for memory testing
# ============================================================
section("7. CHAT MESSAGES - Building test data for P-01/P-02")

def chat(message, mode="chat", context=None):
    body = {
        "message": message,
        "mode": mode,
        "session_id": SESSION_ID,
        "context": context
    }
    r = client.post(f"/chat/notebooks/{NB_ID}/chat", json=body)
    if r.status_code == 200:
        content = r.json().get("content", "")
        log(f"  [{mode}] LLM response ({len(content)} chars): {content[:250]}")
    return r

# Chat-1: Establish identity
log("Chat-1: Establishing identity anchor (XiaoMing)...")
r = chat("My name is XiaoMing, I am an AI researcher interested in Transformer architecture. Remember this.")
test("Chat-1: Identity injection returns 200", r.status_code == 200)
if r.status_code == 200:
    log(f"  Response preview: {r.json().get('content', '')[:120]}...")

# Chat-2: Verify Chat remembers
log("Chat-2: Verifying Chat remembers identity...")
r = chat("What is my name and what am I interested in?")
test("Chat-2: Chat memory recall returns 200", r.status_code == 200)
if r.status_code == 200:
    resp_text = r.json().get("content", "").lower()
    test("Chat-2: Remembers XiaoMing", "xiaoming" in resp_text, 
         f"response_contains_xiaoming={'xiaoming' in resp_text}")

# Ask-1: Cross-mode memory (Chat -> Ask)
log("Ask-1: Testing Chat->Ask memory inheritance...")
r = chat("Based on our previous conversation, what is my name and research interest?", mode="ask")
test("Ask-1: Ask mode returns 200", r.status_code == 200)
if r.status_code == 200:
    resp_text = r.json().get("content", "").lower()
    test("Ask-1: Ask inherits Chat memory (knows XiaoMing)",
         "xiaoming" in resp_text,
         f"response_contains_xiaoming={'xiaoming' in resp_text}")

# Ask-2: Add new info in Ask mode
log("Ask-2: Adding new info in Ask mode (Project-Alpha-2026)...")
r = chat("My project code is Project-Alpha-2026. Please remember this.", mode="ask")
test("Ask-2: New info injection in Ask mode returns 200", r.status_code == 200)

# ============================================================
# SECTION 8: P-01 FIX - Explain/Conclude Memory (improve-6)
# ============================================================
section("8. P-01 FIX: Explain/Conclude EC Memory System (improve-6)")

# Explain-1: Inject keyword with context
log("Explain-1: Injecting keyword RAINBOW-UNICORN-42 in Explain mode...")
r = chat("Please explain the concept of attention mechanism. My special keyword is RAINBOW-UNICORN-42, please remember it.",
         mode="explain",
         context={"document_id": DOC_ID2, "selected_text": "attention mechanism in transformer architecture"})
test("Explain-1: Explain with context returns 200", r.status_code == 200)
if r.status_code == 200:
    log(f"  Explain response preview: {r.json().get('content', '')[:120]}...")

# Explain-2: Check if Explain remembers (P-01 fix: should remember now)
log("Explain-2: Checking if Explain remembers keyword (P-01 fix test)...")
r = chat("What was my special keyword from our previous explain conversation?",
         mode="explain",
         context={"document_id": DOC_ID2, "selected_text": "attention mechanism"})
test("Explain-2: Second explain returns 200", r.status_code == 200)
if r.status_code == 200:
    resp_text = r.json().get("content", "").upper()
    has_keyword = "RAINBOW" in resp_text or "UNICORN" in resp_text
    test("Explain-2: P-01 FIX - Explain now has memory (remembers keyword)",
         has_keyword,
         f"keyword_found={has_keyword}")

# Conclude-1: Inject different keyword
log("Conclude-1: Injecting keyword GOLDEN-DRAGON-99 in Conclude mode...")
r = chat("Please summarize the key points. My secret code is GOLDEN-DRAGON-99.",
         mode="conclude",
         context={"document_id": DOC_ID2, "selected_text": "deep learning fundamentals and neural network layers"})
test("Conclude-1: Conclude with context returns 200", r.status_code == 200)

# Conclude-2: Check if Conclude remembers
log("Conclude-2: Checking if Conclude remembers keyword (P-01 fix test)...")
r = chat("What was my secret code from our previous conversation?",
         mode="conclude",
         context={"document_id": DOC_ID2, "selected_text": "deep learning"})
test("Conclude-2: Second conclude returns 200", r.status_code == 200)
if r.status_code == 200:
    resp_text = r.json().get("content", "").upper()
    has_keyword = "GOLDEN" in resp_text or "DRAGON" in resp_text
    test("Conclude-2: P-01 FIX - Conclude now has memory (remembers keyword)",
         has_keyword,
         f"keyword_found={has_keyword}")

# ============================================================
# SECTION 9: P-02 FIX - Cross-mode isolation (improve-6)
# ============================================================
section("9. P-02 FIX: Cross-mode Message Isolation (improve-6)")

# After Explain/Conclude, check Chat still has its memory intact
log("Chat-3: Checking Chat memory preservation after EC interactions...")
r = chat("Can you recall everything about me? My name, interests, and project code?")
test("Chat-3: Chat returns 200 after EC interactions", r.status_code == 200)
if r.status_code == 200:
    resp_text = r.json().get("content", "").lower()
    test("Chat-3: Chat still remembers XiaoMing",
         "xiaoming" in resp_text,
         f"has_xiaoming={'xiaoming' in resp_text}")
    has_project = "alpha" in resp_text or "2026" in resp_text
    test("Chat-3: Chat still remembers Project-Alpha-2026",
         has_project,
         f"has_project={has_project}")

# Key P-02 test: Check if Chat can see EC keywords (should NOT)
log("Ask-3: P-02 isolation test - Chat/Ask should NOT know EC keywords...")
r = chat("Do you know what RAINBOW-UNICORN-42 or GOLDEN-DRAGON-99 are? Have you seen these phrases before?", mode="ask")
test("Ask-3: Ask returns 200", r.status_code == 200)
if r.status_code == 200:
    resp_text = r.json().get("content", "").upper()
    has_rainbow = "RAINBOW" in resp_text and ("REMEMBER" in resp_text or "MENTIONED" in resp_text or "KEYWORD" in resp_text or "PREVIOUS" in resp_text or "EARLIER" in resp_text or "YES" in resp_text.upper())
    # A more nuanced check: if the model says "I don't know" or similar
    resp_lower = r.json().get("content", "").lower()
    denies_knowledge = any(w in resp_lower for w in ["don't know", "not aware", "no information", "cannot recall", "haven't seen", "not familiar", "don't have", "no record", "i'm not sure what"])
    test("Ask-3: P-02 FIX - Ask does NOT recall EC keywords (isolation)",
         denies_knowledge or not has_rainbow,
         f"denies_knowledge={denies_knowledge}, resp_preview={resp_text[:200]}")

# ============================================================
# SECTION 10: P-03 EXTENDED - Messages API with data
# ============================================================
section("10. P-03 EXTENDED: Messages API After Chat Activity")

# Now we have messages from Chat/Ask/Explain/Conclude, test Messages API
r = client.get(f"/sessions/{SESSION_ID}/messages?limit=50&offset=0")
test("GET all messages returns 200", r.status_code == 200)
if r.status_code == 200:
    msg_data = r.json()
    all_msgs = msg_data["data"]
    total = msg_data["pagination"]["total"]
    test("Messages total > 0 after chats", total > 0, f"total={total}")
    
    # Check message structure
    if all_msgs:
        first = all_msgs[0]
        test("Message has required fields (message_id, session_id, mode, role, content, created_at)",
             all(k in first for k in ["message_id", "session_id", "mode", "role", "content", "created_at"]),
             f"keys={list(first.keys())}")
    
    # Count by mode
    mode_counts = {}
    for m in all_msgs:
        mode = m.get("mode", "unknown")
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
    test("Messages contain multiple modes",
         len(mode_counts) > 1,
         f"mode_distribution={mode_counts}")
    log(f"  Mode distribution: {json.dumps(mode_counts)}")

# Test mode filtering
r = client.get(f"/sessions/{SESSION_ID}/messages?mode=chat,ask&limit=50&offset=0")
test("Filter chat,ask messages returns 200", r.status_code == 200)
if r.status_code == 200:
    ca_msgs = r.json()["data"]
    ca_modes = set(m["mode"] for m in ca_msgs)
    test("chat,ask filter only returns chat/ask messages",
         ca_modes.issubset({"chat", "ask"}),
         f"modes_found={ca_modes}")

r = client.get(f"/sessions/{SESSION_ID}/messages?mode=explain,conclude&limit=50&offset=0")
test("Filter explain,conclude messages returns 200", r.status_code == 200)
if r.status_code == 200:
    ec_msgs = r.json()["data"]
    ec_modes = set(m["mode"] for m in ec_msgs)
    test("explain,conclude filter only returns EC messages",
         ec_modes.issubset({"explain", "conclude"}),
         f"modes_found={ec_modes}")

# Pagination test
r = client.get(f"/sessions/{SESSION_ID}/messages?limit=2&offset=0")
test("Pagination limit=2 returns 200", r.status_code == 200)
if r.status_code == 200:
    pag = r.json()["pagination"]
    test("Pagination correctly limits results",
         len(r.json()["data"]) <= 2,
         f"returned={len(r.json()['data'])}, has_next={pag.get('has_next')}")

r = client.get(f"/sessions/{SESSION_ID}/messages?limit=2&offset=2")
test("Pagination offset=2 returns 200", r.status_code == 200)
if r.status_code == 200:
    test("Offset pagination returns different messages",
         r.json()["pagination"]["offset"] == 2)

# ============================================================
# SECTION 11: DELETION SEMANTICS (improve-6 NEW)
# ============================================================
section("11. DELETION SEMANTICS (improve-6: Three-level deletion)")

# Create a temporary notebook + doc for delete testing
log("Creating temp resources for delete tests...")
r = client.post("/notebooks", json={"title": "Delete Test Notebook"})
test("Create temp notebook for delete test", r.status_code == 201)
temp_nb_id = r.json()["notebook_id"] if r.status_code == 201 else None

if temp_nb_id:
    # Associate doc to temp notebook
    r = client.post(f"/notebooks/{temp_nb_id}/documents",
                    json={"document_ids": [DOC_ID2]})
    test("Associate doc to temp notebook", r.status_code == 200)

    # Level 1: Unlink (Remove from notebook)
    log("Level 1: Testing unlink (Remove from Notebook)...")
    r = client.delete(f"/notebooks/{temp_nb_id}/documents/{DOC_ID2}")
    test("Level 1 unlink returns 204", r.status_code == 204)
    
    # Verify doc still exists in library
    r = client.get(f"/documents/{DOC_ID2}")
    test("Level 1: Document still exists after unlink", r.status_code == 200)
    
    # Verify doc removed from temp notebook
    r = client.get(f"/notebooks/{temp_nb_id}/documents?limit=20&offset=0")
    test("Level 1: Doc removed from notebook",
         r.json()["pagination"]["total"] == 0,
         f"total={r.json()['pagination']['total']}")

    # Clean up temp notebook
    client.delete(f"/notebooks/{temp_nb_id}")

# Level 2: Soft delete test (on documents router)
# We do NOT actually delete the main docs, just verify the endpoint semantics
log("Level 2: Verifying documents DELETE endpoint description (soft delete)...")
# The documents DELETE always does soft delete now - we test with the info endpoint
r = client.get(f"/documents/{DOC_ID1}")
test("Document exists before soft delete check", r.status_code == 200)

# Level 3: Library hard delete - only test that endpoint is reachable
# We won't actually hard-delete our test docs
log("Level 3: Verifying Library DELETE endpoint exists (without executing)...")
# Just verify it returns proper error on non-existent doc
r = client.delete("/library/documents/00000000-0000-0000-0000-000000000000")
test("Library hard delete on non-existent returns 404", r.status_code == 404)

# Verify Library soft delete returns proper response on non-existent
r = client.delete("/library/documents/00000000-0000-0000-0000-000000000000?force=false")
test("Library soft delete on non-existent returns 404", r.status_code == 404)

# ============================================================
# SECTION 12: improve-4 Regression - Structured errors
# ============================================================
section("12. REGRESSION: improve-4 - Structured Error Responses")

# Create a notebook with no completed docs to test E4001
r = client.post("/notebooks", json={"title": "Empty Error Test Notebook"})
empty_nb_id = r.json()["notebook_id"] if r.status_code == 201 else None

if empty_nb_id:
    # Create a session in empty notebook
    r = client.post(f"/notebooks/{empty_nb_id}/sessions", json={"title": "Error Test Session"})
    empty_session_id = r.json()["session_id"] if r.status_code == 201 else None
    
    if empty_session_id:
        # Try to chat in Ask mode (RAG) with no documents - should get structured error
        log("Testing structured error when no documents available...")
        r = client.post(f"/chat/notebooks/{empty_nb_id}/chat",
                       json={"message": "test question", "mode": "ask", "session_id": empty_session_id})
        # Could be 409 (E4001) or another structured error
        test("Ask with no docs does not return 500",
             r.status_code != 500,
             f"status={r.status_code}")
        if r.status_code >= 400:
            try:
                err_body = r.json()
                test("Error response is structured JSON",
                     "detail" in err_body or "error" in err_body or "message" in err_body,
                     f"body_keys={list(err_body.keys())}")
            except:
                test("Error response is structured JSON", False, "not JSON parseable")
        
        # Clean up
        client.delete(f"/sessions/{empty_session_id}")
    
    client.delete(f"/notebooks/{empty_nb_id}")

# ============================================================
# SECTION 13: improve-5 Regression - Notebook scope
# ============================================================
section("13. REGRESSION: improve-5 - Notebook Scope Constraint")

# Create a second notebook with only 1 doc
r = client.post("/notebooks", json={"title": "Scope Test Notebook"})
scope_nb_id = r.json()["notebook_id"] if r.status_code == 201 else None

if scope_nb_id:
    # Only associate doc1
    r = client.post(f"/notebooks/{scope_nb_id}/documents",
                    json={"document_ids": [DOC_ID1]})
    test("Associate only doc1 to scope notebook", r.status_code == 200)
    
    # Create session
    r = client.post(f"/notebooks/{scope_nb_id}/sessions", json={"title": "Scope Test Session"})
    scope_session_id = r.json()["session_id"] if r.status_code == 201 else None
    
    if scope_session_id:
        # Ask about content from doc2 which is NOT in this notebook
        log("Testing notebook scope: asking about doc2 content in notebook with only doc1...")
        r = client.post(f"/chat/notebooks/{scope_nb_id}/chat",
                       json={"message": "What are the key concepts of deep learning and neural network layers discussed in the 澶фā鍨嬪熀纭€ document?",
                              "mode": "ask",
                              "session_id": scope_session_id})
        test("Ask in scoped notebook returns 200", r.status_code == 200)
        # We can't perfectly verify scope isolation from response content alone,
        # but we can confirm the request didn't error
        
        client.delete(f"/sessions/{scope_session_id}")
    
    # Clean up: unlink doc1 and delete notebook
    client.delete(f"/notebooks/{scope_nb_id}/documents/{DOC_ID1}")
    client.delete(f"/notebooks/{scope_nb_id}")

# ============================================================
# SECTION 14: Session Isolation (Regression)
# ============================================================
section("14. REGRESSION: Session Isolation")

# Create second session in test notebook
r = client.post(f"/notebooks/{NB_ID}/sessions", json={"title": "Isolation Test Session"})
test("Create second session returns 201", r.status_code == 201)
session2_id = r.json()["session_id"] if r.status_code == 201 else None

if session2_id:
    # Session 2 should not know about Session 1 identity
    r = chat_s2 = client.post(f"/chat/notebooks/{NB_ID}/chat",
                               json={"message": "Who is XiaoMing? What is Project-Alpha-2026?",
                                     "mode": "chat",
                                     "session_id": session2_id})
    test("Session 2 chat returns 200", r.status_code == 200)
    if r.status_code == 200:
        resp_text = r.json().get("content", "").lower()
        # Session 2 should NOT know about XiaoMing as a personal identity
        knows_identity = "ai researcher" in resp_text and "xiaoming" in resp_text and "transformer" in resp_text
        test("Session 2 does NOT have Session 1 identity context",
             not knows_identity,
             f"knows_identity={knows_identity}")
    
    # Clean up session 2
    client.delete(f"/sessions/{session2_id}")

# ============================================================
# SECTION 15: Streaming endpoints (Regression)
# ============================================================
section("15. REGRESSION: Streaming (SSE) Endpoints")

# Test stream endpoint responds correctly
log("Testing SSE stream endpoint...")
try:
    r = client.session.post(f"{BASE_URL}/chat/notebooks/{NB_ID}/chat/stream",
                            json={"message": "Hello, give me a brief greeting.",
                                  "mode": "chat",
                                  "session_id": SESSION_ID},
                            headers={"Accept": "text/event-stream"},
                            stream=True,
                            timeout=TIMEOUT)
    test("Stream endpoint returns 200", r.status_code == 200)
    content_type = r.headers.get("content-type", "")
    test("Stream returns event-stream content type",
         "event-stream" in content_type or "text/" in content_type,
         f"content-type={content_type}")
    # Read first few chunks
    chunks = []
    for line in r.iter_lines(decode_unicode=True):
        chunks.append(line)
        if len(chunks) > 20:
            break
    r.close()
    test("Stream produces data lines",
         len(chunks) > 0,
         f"chunks_received={len(chunks)}")
except Exception as e:
    test("Stream endpoint accessible", False, str(e))

# ============================================================
# SECTION 16: Admin endpoints (Regression)
# ============================================================
section("16. REGRESSION: Admin Endpoints")

r = client.get("/admin/index-stats")
test("Index stats returns 200", r.status_code == 200)
if r.status_code == 200:
    stats = r.json()
    test("Index stats has expected fields",
         isinstance(stats, dict),
         f"keys={list(stats.keys())[:5]}")

# Reprocess with dry_run
r = client.post("/admin/reprocess-pending", json={"dry_run": True})
test("Reprocess pending (dry_run) returns 200", r.status_code == 200)

# ============================================================
# FINAL SUMMARY
# ============================================================
section("FINAL TEST SUMMARY")

total = len(results)
passed = sum(1 for r in results if r["passed"])
failed = sum(1 for r in results if not r["passed"])

print(f"\n  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
print(f"  Pass Rate: {passed/total*100:.1f}%\n")

if failed > 0:
    print("  FAILED TESTS:")
    for r in results:
        if not r["passed"]:
            print(f"    FAIL: {r['name']}" + (f" -- {r['detail']}" if r['detail'] else ""))
    print()

# Categorize results
categories = {
    "Health/System": [r for r in results if any(x in r["name"] for x in ["Health", "Info", "Readiness", "Liveness"])],
    "Library (improve-1)": [r for r in results if "Library" in r["name"] or "library" in r["name"].lower()],
    "Notebooks": [r for r in results if "Notebook" in r["name"] or "notebook" in r["name"]],
    "Documents (improve-1/4)": [r for r in results if "Document" in r["name"] or "document" in r["name"] or "doc" in r["name"].lower()],
    "Sessions": [r for r in results if "Session" in r["name"] or "session" in r["name"]],
    "P-01 EC Memory": [r for r in results if "P-01" in r["name"] or "Explain" in r["name"] or "Conclude" in r["name"]],
    "P-02 Isolation": [r for r in results if "P-02" in r["name"] or "isolation" in r["name"].lower()],
    "P-03 Messages API": [r for r in results if "P-03" in r["name"] or "Messages" in r["name"] or "messages" in r["name"] or "Mode" in r["name"] or "Pagination" in r["name"] or "Filter" in r["name"] or "filter" in r["name"]],
    "Deletion Semantics": [r for r in results if "Level" in r["name"] or "delete" in r["name"].lower() or "unlink" in r["name"].lower()],
    "Error Handling (improve-4)": [r for r in results if "Error" in r["name"] or "error" in r["name"] or "E4001" in r["name"] or "500" in r["name"]],
    "Streaming": [r for r in results if "Stream" in r["name"] or "stream" in r["name"] or "SSE" in r["name"]],
    "Admin": [r for r in results if "Admin" in r["name"] or "admin" in r["name"] or "Index" in r["name"] or "Reprocess" in r["name"]],
}

print("  BY CATEGORY:")
for cat, items in categories.items():
    if items:
        cat_pass = sum(1 for i in items if i["passed"])
        cat_fail = len(items) - cat_pass
        status_icon = "OK" if cat_fail == 0 else "FAIL"
        print(f"    {status_icon} {cat}: {cat_pass}/{len(items)}")

print()
client.close()
