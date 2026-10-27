import io
import json
import re
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import summarizer


class Clock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class Gemini:
    def __init__(self):
        self.steps = []
        self.calls = []
        self.default = self.smart

    def add(self, *steps):
        self.steps.extend(steps)

    def smart(self, call):
        prompt = call["prompt"]
        numbers = re.findall(r'<bab nomor="(\d+)"', prompt)
        if numbers:
            return ("text", json.dumps({"bab": [{"nomor": int(n), "rangkuman": f"Rangkuman bab {n}."} for n in numbers]}))
        if "<rangkuman>" in prompt:
            return ("text", "Rangkuman keseluruhan.")
        return ("text", "Rangkuman tunggal.")

    def __call__(self, req, timeout=None):
        payload = json.loads(req.data)
        call = {
            "url": req.full_url,
            "model": re.search(r"models/([^:]+):", req.full_url).group(1),
            "prompt": payload["contents"][0]["parts"][0]["text"],
            "key": req.get_header("X-goog-api-key"),
            "body": payload,
        }
        self.calls.append(call)
        step = self.steps.pop(0) if self.steps else self.default
        if callable(step):
            step = step(call)
        kind = step[0]
        if kind == "text":
            body = {"candidates": [{"content": {"parts": [{"text": step[1]}]}}]}
            if len(step) > 2:
                body["usageMetadata"] = step[2]
            return io.BytesIO(json.dumps(body).encode())
        if kind == "parts":
            return io.BytesIO(json.dumps({"candidates": [{"content": {"parts": [{"text": t} for t in step[1]]}}]}).encode())
        if kind == "json":
            return io.BytesIO(json.dumps(step[1]).encode())
        if kind == "http":
            raise urllib.error.HTTPError(req.full_url, step[1], "galat", {}, io.BytesIO(step[2].encode()))
        if kind == "net":
            raise urllib.error.URLError("jaringan putus")
        raise AssertionError(f"langkah tak dikenal: {kind}")

    def batch_prompts(self):
        return [c for c in self.calls if "<bab nomor=" in c["prompt"]]

    def single_prompts(self):
        return [c for c in self.calls if "Rangkum bab berjudul" in c["prompt"]]

    def overall_prompts(self):
        return [c for c in self.calls if "<rangkuman>" in c["prompt"]]


DAILY_429 = '{"error":{"message":"Quota exceeded for metric GenerateRequestsPerDayPerProjectPerModel"}}'
MINUTE_429 = '{"error":{"message":"Quota exceeded for metric GenerateRequestsPerMinutePerProjectPerModel"}}'


def minute_429(delay):
    return '{"error":{"details":[{"retryDelay":"%ss"}]}}' % delay


@pytest.fixture
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(summarizer, "time", SimpleNamespace(monotonic=c.monotonic, sleep=c.sleep))
    return c


@pytest.fixture
def gemini(monkeypatch, clock):
    fake = Gemini()
    monkeypatch.setattr(urllib.request, "urlopen", fake)
    monkeypatch.setattr(settings, "gemini_api_key", "kunci-rahasia")
    monkeypatch.setattr(settings, "gemini_model", "m1")
    monkeypatch.setattr(settings, "gemini_fallback_model", "")
    monkeypatch.setattr(settings, "gemini_min_interval", 0.0)
    monkeypatch.setattr(summarizer, "_last_call", 0.0)
    summarizer._blocked.clear()
    yield fake
    summarizer._blocked.clear()
