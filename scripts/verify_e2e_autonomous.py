import subprocess
import time
import sys
import os
import httpx
import http.server
import threading

class MockRSSHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/feed.xml":
            self.send_response(200)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.end_headers()
            rss_content = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
  <channel>
    <title>Mock AI Security Feed</title>
    <link>http://127.0.0.1:8001/</link>
    <description>Mock feed for E2E testing</description>
    <item>
      <title>Transformer model vulnerabilities zero-day jailbreak exploit discovered</title>
      <link>https://techcrunch.com/mock-vulnerability-paper</link>
      <description>A newly discovered token alignment attack bypasses guardrails on current LLMs.</description>
      <pubDate>Sun, 09 Aug 2026 06:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
            self.wfile.write(rss_content.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress logging to keep console clean
        return

def main():
    print("======================================================================")
    print("STARTING HACKATHON EVALUATOR TIME-BASED AUTONOMOUS RUNTIME SIMULATION")
    print("======================================================================")

    # 1. Start the local mock RSS feed server
    print("[STEP 1] Starting mock RSS feed server on port 8001...")
    mock_server = http.server.HTTPServer(("127.0.0.1", 8001), MockRSSHandler)
    mock_server_thread = threading.Thread(target=mock_server.serve_forever)
    mock_server_thread.daemon = True
    mock_server_thread.start()
    print("✔ Mock RSS server is listening at http://127.0.0.1:8001/feed.xml")

    # Configure env to run loop frequently (every 2 seconds) for fast verification
    env = os.environ.copy()
    env["AUTONOMOUS_INTERVAL_SECONDS"] = "2.0"
    env["DISCOVERY_TIMEOUT_SECONDS"] = "10.0"
    env["AUTONOMOUS_ENABLED"] = "True"
    env["DISCOVERY_FEEDS"] = '["http://127.0.0.1:8001/feed.xml"]'

    # 2. Start the FastAPI server on port 8000
    print("\n[STEP 2] Starting FastAPI dev server subprocess on port 8000...")
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"]
    server_process = subprocess.Popen(
        cmd,
        env=env
    )

    # Give uvicorn server 2.5 seconds to bind to port and startup
    time.sleep(2.5)

    client = httpx.Client(timeout=10.0)
    agent_id = None

    try:
        # Check health check route
        print("\n[STEP 3] Checking server health...")
        health_resp = client.get("http://127.0.0.1:8000/health")
        assert health_resp.status_code == 200, f"Expected 200 health, got {health_resp.status_code}"
        print("✔ Health Check SUCCESS.")

        # Simulate Evaluator: POST /api/agent/init exactly once
        print("\n[STEP 4] Calling POST /api/agent/init exactly once...")
        init_payload = {
            "persona": {
                "name": "Ada",
                "domain": "AI Security"
            }
        }
        init_resp = client.post("http://127.0.0.1:8000/api/agent/init", json=init_payload)
        assert init_resp.status_code == 200, f"Expected 200 initialization, got {init_resp.status_code}"
        agent_id = init_resp.json()["agentId"]
        print(f"✔ Agent initialized successfully. Received agentId: {agent_id}")

        # Simulate Evaluator: DO NOTHING. Wait for loops to run autonomously
        print("\n[STEP 5] Waiting 5.0 seconds for background scheduler cycles to execute...")
        time.sleep(5.0)

        # Retrieve published feed
        print("\n[STEP 6] Querying GET /api/agent/feed?agentId=...")
        feed_resp = client.get(f"http://127.0.0.1:8000/api/agent/feed?agentId={agent_id}")
        assert feed_resp.status_code == 200, f"Expected 200 feed response, got {feed_resp.status_code}"
        feed_data = feed_resp.json()
        posts = feed_data["posts"]
        print(f"Current Feed Count: {len(posts)}")
        assert len(posts) > 0, "Autonomous scheduler failed to publish any posts after 5 seconds!"
        
        # Verify post schema constraints
        first_post = posts[0]
        assert "id" in first_post and len(first_post["id"]) > 0
        assert "createdAt" in first_post
        assert "text" in first_post and len(first_post["text"]) > 0
        assert "rationale" in first_post and len(first_post["rationale"]) > 0
        assert "sources" in first_post and len(first_post["sources"]) > 0
        print(f"✔ First post schema verified. (ID: {first_post['id']})")
        print(f"✔ Rationale: {first_post['rationale']}")

        # Retrieve status endpoint to verify persona load matching
        print("\n[STEP 7] Querying UI status endpoint GET /api/agent/status?agentId=...")
        status_resp = client.get(f"http://127.0.0.1:8000/api/agent/status?agentId={agent_id}")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert status_data["agentId"] == agent_id
        assert status_data["persona"]["name"] == "Ada"
        print("✔ Status details matches active agent persona.")

        # Wait another 5.0 seconds to test deduplication and persistence stability
        print("\n[STEP 8] Waiting another 5.0 seconds to test deduplication guard...")
        time.sleep(5.0)

        # Retrieve feed again
        feed_resp_2 = client.get(f"http://127.0.0.1:8000/api/agent/feed?agentId={agent_id}")
        feed_data_2 = feed_resp_2.json()
        posts_2 = feed_data_2["posts"]
        print(f"Feed Count after additional wait: {len(posts_2)}")

        # Deduplication check: check for duplicates
        ids = [p["id"] for p in posts_2]
        assert len(ids) == len(set(ids)), "Deduplication failure: duplicate post IDs found in feed!"
        print("✔ Deduplication SUCCESS: No duplicate post IDs created.")

        # Check chronological ordering: newest first
        from datetime import datetime
        def parse_created_at(p):
            return datetime.fromisoformat(p["createdAt"].replace("Z", "+00:00"))
        
        timestamps = [parse_created_at(p) for p in posts_2]
        sorted_timestamps = sorted(timestamps, reverse=True)
        assert timestamps == sorted_timestamps, "Chronological ordering check failed! Feed must be sorted newest first."
        print("✔ Chronological ordering (newest first) SUCCESS.")

        print("\n======================================================================")
        print("E2E TIME-BASED AUTONOMOUS PIPELINE VALIDATION COMPLETED SUCCESSFULLY!")
        print("======================================================================")

    except Exception as e:
        print(f"\n❌ E2E VALIDATION ERROR: {e}")
        sys.exit(1)
        
    finally:
        print("[CLEANUP] Stopping FastAPI server subprocess...")
        server_process.terminate()
        server_process.wait()
        mock_server.shutdown()
        print("Server process and mock RSS server shut down successfully.")

if __name__ == "__main__":
    main()
