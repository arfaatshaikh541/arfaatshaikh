"""Exercises OllamaProvider's success path against a real local HTTP server
that implements Ollama's documented /api/tags and /api/generate response
shapes - not a mock of httpx, an actual TCP server this test's client
connects to over the loopback interface.

This is NOT a test against the real Ollama binary: this sandbox's network
egress to ollama.com is blocked by policy (verified: `curl ollama.com`
returns a policy-rejected CONNECT) and no apt/system package for the
Ollama *server* exists here (only an unrelated PyPI "ollama" *client SDK*
package). See docs/ai/provider-architecture.md and
docs/FINAL_AUDIT_ULTIMATE.md for that distinction spelled out - the
absence-of-Ollama path is verified for real in test_ai_provider.py; this
file only proves OllamaProvider parses a correctly-shaped success response
the way the real server is documented to send one.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from app.services.ai_provider import OllamaProvider


class _FakeOllamaHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence test output
        pass

    def do_GET(self):
        if self.path == "/api/tags":
            body = json.dumps({"models": [{"name": "llama3.1"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        request_body = json.loads(self.rfile.read(length) or b"{}")
        assert request_body["model"] == "llama3.1"
        assert "prompt" in request_body
        body = json.dumps({
            "model": "llama3.1",
            "response": "Patience (sabr) is repeatedly emphasized in the Qur'an.",
            "done": True,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def fake_ollama_server():
    server = HTTPServer(("127.0.0.1", 0), _FakeOllamaHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)


async def test_ollama_provider_reports_available_against_a_conforming_server(fake_ollama_server):
    provider = OllamaProvider(base_url=fake_ollama_server, model="llama3.1", timeout_seconds=5.0)
    assert await provider.is_available() is True


async def test_ollama_provider_parses_a_real_success_response(fake_ollama_server):
    provider = OllamaProvider(base_url=fake_ollama_server, model="llama3.1", timeout_seconds=5.0)
    result = await provider.generate("What does the Qur'an say about patience?")
    assert result.available is True
    assert result.provider == "ollama"
    assert result.error is None
    assert "sabr" in (result.text or "").lower() or "patience" in (result.text or "").lower()
