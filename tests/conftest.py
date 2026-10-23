import json
import os
import sys
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
}
os.environ.update(TEST_ENV)
for name in ("ANTHROPIC_API_KEY", "DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME",
             "QDRANT_HOST", "QDRANT_COLLECTION", "VOYAGE_API_KEY"):
    os.environ.setdefault(name, "test")
os.environ.setdefault("QDRANT_PORT", "6333")


# --- Fake AI graph: records what the chat endpoint asked for ----------------
class FakeGraph:
    def __init__(self):
        self.calls = []

    error = None

    def invoke(self, state):
        self.calls.append(state)
        if self.error is not None:
            raise self.error
        return {**state, "answer": f"answer from {state['collection']}", "meta_data": None}


fake_graph = FakeGraph()
graph_module = types.ModuleType("app.graph.chat_graph")
graph_module.graph = fake_graph
sys.modules["app.graph.chat_graph"] = graph_module


# --- The app's in-memory store, cleared between tests ----------------------
from app.config.memory_store import memory_store as fake_redis  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.config.settings import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.services.llm_config_service import llm_config_service  # noqa: E402
from app.services.question_limit_service import question_limit_service  # noqa: E402
from app.services.site_collection_service import site_collection_service  # noqa: E402
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


class FakeDjangoLLM:
    """Mock of Django's POST /api/internal/chatbot/llm-config/ (same contract)."""

    def __init__(self):
        self.calls = []
        self.configs = {}  # site_id -> response JSON; missing = llm_not_configured
        self.override = None

    def handler(self, request):
        body = json.loads(request.content)
        self.calls.append({"auth": request.headers.get("Authorization"), "body": body, "url": str(request.url)})
        if self.override is not None:
            return self.override(request)
        config = self.configs.get(body.get("site_id"))
        if config is None:
            return httpx.Response(404, json={"error": "llm_not_configured"})
        return httpx.Response(200, json=config)


class FakeDjangoQuestions:
    """Mock of Django's questions/consume/ and questions/refund/ (same contract)."""

    def __init__(self):
        self.calls = []
        self.limits = {}  # site_id -> limit (missing/0 = unlimited)
        self.counts = {}  # (site_id, visitor_id) -> used
        self.override = None

    def handler(self, request):
        body = json.loads(request.content)
        action = request.url.path.rstrip("/").rsplit("/", 1)[-1]
        self.calls.append({"action": action, "body": body, "auth": request.headers.get("Authorization"),
                           "url": str(request.url)})
        if self.override is not None:
            return self.override(request)

        key = (body["site_id"], body["visitor_id"])
        limit = self.limits.get(body["site_id"], 0)
        if action == "refund":
            self.counts[key] = max(self.counts.get(key, 0) - 1, 0)
            return httpx.Response(200, json={"refunded": True})
        if not limit:
            return httpx.Response(200, json={"allowed": True, "limit": 0, "remaining": None, "period": "day", "resets_at": None})
        used = self.counts.get(key, 0)
        if used >= limit:
            return httpx.Response(200, json={
                "allowed": False, "limit": limit, "remaining": 0, "period": "day",
                "resets_at": "2099-01-01T00:00:00Z", "reason": "question_limit",
                "message": "You have used all 2 questions for today.",
            })
        self.counts[key] = used + 1
        return httpx.Response(200, json={"allowed": True, "limit": limit, "remaining": limit - used - 1,
                                         "period": "day", "resets_at": "2099-01-01T00:00:00Z"})


# Rows of django_app.websites_website by id (only the columns the app reads).
django_websites = {}


def fake_websites_fetch(site_id):
    row = django_websites.get(str(site_id))
    if isinstance(row, Exception):
        raise row
    return types.SimpleNamespace(**row) if row else None


@pytest.fixture
def django():
    return FakeDjango()


@pytest.fixture
def django_llm():
    return FakeDjangoLLM()


@pytest.fixture
def django_questions():
    return FakeDjangoQuestions()


@pytest.fixture(autouse=True)
def isolate(django, django_llm, django_questions, monkeypatch):
    fake_redis.data.clear()
    fake_redis.expiry.clear()
    fake_graph.calls.clear()
    fake_graph.error = None
    for name, value in TEST_ENV.items():
        monkeypatch.setattr(settings, name, value)
    django_websites.clear()
    django_websites.update({
        SITE_A["site_id"]: {"collection_name": "companiesnext", "is_active": 1},
        SITE_B["site_id"]: {"collection_name": "othercustomer_kb", "is_active": 1},
    })
    monkeypatch.setattr(site_collection_service, "_fetch", fake_websites_fetch)
    monkeypatch.setattr(subscription_service, "_client", httpx.AsyncClient(transport=httpx.MockTransport(django.handler)))
    monkeypatch.setattr(llm_config_service, "_client", httpx.AsyncClient(transport=httpx.MockTransport(django_llm.handler)))
    llm_config_service.clear()
    monkeypatch.setattr(question_limit_service, "_client", httpx.AsyncClient(transport=httpx.MockTransport(django_questions.handler)))
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
