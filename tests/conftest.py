import fnmatch
import json
import os
import sys
import time
import types

import httpx
import pytest

# --- Environment: test values only, never production credentials -----------
TEST_ENV = {
    "APP_ENV": "production",
    "DJANGO_SUBSCRIPTION_VERIFY_URL": "https://django.test/api/internal/chatbot/verify-subscription/",
    "DJANGO_SERVICE_API_KEY": "test-django-service-key",
    "WIDGET_JWT_SECRET": "test-widget-jwt-secret-0123456789abcdef",
    "INTERNAL_SERVICE_TOKENS": "test-internal-token",
    "WIDGET_ALLOWED_ORIGINS": "",
    "WIDGET_DEV_DOMAIN": "",
    "WIDGET_SITE_COLLECTIONS": "{}",
}
os.environ.update(TEST_ENV)
for name in ("ANTHROPIC_API_KEY", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME",
             "QDRANT_HOST", "QDRANT_COLLECTION", "VOYAGE_API_KEY", "HF_TOKEN"):
    os.environ.setdefault(name, "test")
os.environ.setdefault("QDRANT_PORT", "6333")


# --- Fake AI graph: records what the chat endpoint asked for ----------------
class FakeGraph:
    def __init__(self):
        self.calls = []

    def invoke(self, state):
        self.calls.append(state)
        return {**state, "answer": f"answer from {state['collection']}", "meta_data": None}


fake_graph = FakeGraph()
graph_module = types.ModuleType("app.graph.chat_graph")
graph_module.graph = fake_graph
sys.modules["app.graph.chat_graph"] = graph_module


# --- In-memory Redis with expiry, enough for the commands the app uses -------
class FakeRedis:
    def __init__(self):
        self.data = {}
        self.expiry = {}

    def _alive(self, key):
        if key in self.expiry and self.expiry[key] <= time.time():
            self.data.pop(key, None)
            self.expiry.pop(key, None)
        return key in self.data

    def get(self, key):
        return self.data[key] if self._alive(key) else None

    def set(self, key, value, ex=None):
        self.data[key] = str(value)
        if ex:
            self.expiry[key] = time.time() + ex
        else:
            self.expiry.pop(key, None)
        return True

    def incrby(self, key, amount):
        value = int(self.get(key) or 0) + amount
        self.data[key] = str(value)
        return value

    def incr(self, key):
        return self.incrby(key, 1)

    def decr(self, key):
        return self.incrby(key, -1)

    def expire(self, key, seconds):
        if self._alive(key):
            self.expiry[key] = time.time() + seconds

    def delete(self, *keys):
        for key in keys:
            self.data.pop(key, None)
            self.expiry.pop(key, None)

    def rpush(self, key, value):
        self.data.setdefault(key, [])
        self.data[key].append(value)

    def lrange(self, key, start, end):
        values = self.data.get(key, [])
        return values[start:] if end == -1 else values[start:end + 1]

    def keys(self, pattern="*"):
        return [key for key in list(self.data) if self._alive(key) and fnmatch.fnmatch(key, pattern)]


fake_redis = FakeRedis()

from app.config.redis import RedisClient  # noqa: E402

RedisClient().client = fake_redis

from fastapi.testclient import TestClient  # noqa: E402

from app.config.settings import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.subscription_service import subscription_service  # noqa: E402

SITE_A = {"key": "site_" + "a" * 32, "domain": "companiesnext.com", "site_id": "11", "customer_id": "101"}
SITE_B = {"key": "site_" + "b" * 32, "domain": "othercustomer.com", "site_id": "22", "customer_id": "202"}


class FakeDjango:
    """Mock of the Django verify-subscription endpoint (same contract)."""

    def __init__(self):
        self.calls = []
        self.sites = {SITE_A["key"]: dict(SITE_A), SITE_B["key"]: dict(SITE_B)}
        self.override = None  # callable(request) -> httpx.Response, or exception

    def handler(self, request):
        self.calls.append({
            "auth": request.headers.get("Authorization"),
            "body": json.loads(request.content),
        })
        if self.override is not None:
            return self.override(request)

        body = json.loads(request.content)
        site = self.sites.get(body["site_key"])
        if site is None:
            return httpx.Response(403, json={"authorized": False, "reason": "invalid_site_key"})
        if site.get("disabled"):
            return httpx.Response(403, json={"authorized": False, "reason": "site_disabled"})
        if body["domain"] != site["domain"]:
            return httpx.Response(403, json={"authorized": False, "reason": "domain_not_allowed"})
        if site.get("subscription") in ("inactive", "expired"):
            return httpx.Response(403, json={"authorized": False, "reason": f"subscription_{site['subscription']}"})
        return httpx.Response(200, json={
            "authorized": True,
            "site_id": site["site_id"],
            "customer_id": site["customer_id"],
            "plan": "Pro",
            "expires_at": "2099-01-01T00:00:00Z",
        })


@pytest.fixture
def django():
    return FakeDjango()


@pytest.fixture(autouse=True)
def isolate(django, monkeypatch):
    fake_redis.data.clear()
    fake_redis.expiry.clear()
    fake_graph.calls.clear()
    for name, value in TEST_ENV.items():
        if name == "WIDGET_SITE_COLLECTIONS":
            value = {}
        monkeypatch.setattr(settings, name, value)
    monkeypatch.setattr(subscription_service, "_client", httpx.AsyncClient(transport=httpx.MockTransport(django.handler)))
    yield


@pytest.fixture
def client():
    return TestClient(app)


def origin(domain, scheme="https"):
    return {"Origin": f"{scheme}://{domain}"}


def start_session(client, site=SITE_A, domain=None, scheme="https"):
    return client.post(
        "/api/v1/widget/session",
        json={"site_key": site["key"]},
        headers=origin(domain or site["domain"], scheme),
    )


def auth_headers(token, domain):
    return {"Authorization": f"Bearer {token}", **origin(domain)}


@pytest.fixture
def session_token(client):
    response = start_session(client)
    assert response.status_code == 200, response.text
    return response.json()["data"]["token"]
