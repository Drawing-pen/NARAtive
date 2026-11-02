import io
import json
import urllib.error
import urllib.request

import pytest

from app.core.config import settings
from app.services import summarizer

BASE = "https://router.test/v1"
KEY = "kunci-router-rahasia"


class Router:
    """Tiruan endpoint /chat/completions. Langkah: text, filtered, json, http, net, empty."""

    def __init__(self):
        self.steps = []
        self.calls = []
        self.default = ("text", "Dari router")

    def add(self, *steps):
        self.steps.extend(steps)

    def __call__(self, req, timeout=None):
        payload = json.loads(req.data)
        self.calls.append({
            "url": req.full_url,
            "auth": req.get_header("Authorization"),
            "body": payload,
            "prompt": payload["messages"][-1]["content"],
            "system": payload["messages"][0]["content"],
            "timeout": timeout,
        })
        step = self.steps.pop(0) if self.steps else self.default
        kind = step[0]
        if kind == "text":
            body = {"choices": [{"message": {"content": step[1]}, "finish_reason": "stop"}],
                    "usage": {"prompt_tokens": 11, "completion_tokens": 7}}
            return io.BytesIO(json.dumps(body).encode())
        if kind == "filtered":
            return io.BytesIO(json.dumps({"choices": [{"message": {"content": ""}, "finish_reason": "content_filter"}]}).encode())
        if kind == "empty":
            return io.BytesIO(json.dumps({"choices": []}).encode())
        if kind == "json":
            return io.BytesIO(json.dumps(step[1]).encode())
        if kind == "http":
            raise urllib.error.HTTPError(req.full_url, step[1], "galat", {}, io.BytesIO(step[2].encode()))
        if kind == "net":
            raise urllib.error.URLError("jaringan putus")
        raise AssertionError(f"langkah tak dikenal: {kind}")


@pytest.fixture
def router(monkeypatch, gemini):
    fake = Router()
    gemini_urlopen = urllib.request.urlopen

    def dispatch(req, timeout=None):
        if req.full_url.endswith("/chat/completions"):
            return fake(req, timeout)
        return gemini_urlopen(req, timeout)

    monkeypatch.setattr(urllib.request, "urlopen", dispatch)
    monkeypatch.setattr(settings, "router_base_url", BASE)
    monkeypatch.setattr(settings, "router_api_key", KEY)
    monkeypatch.setattr(settings, "router_model", "rm1")
    monkeypatch.setattr(settings, "router_timeout", 120.0)
    monkeypatch.setattr(summarizer, "_router_blocked_until", 0.0)
    return fake
