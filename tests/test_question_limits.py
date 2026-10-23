"""Per-visitor question limit set on each website in Django, enforced by the chat API."""

import httpx
from jose import jwt

from app.config.settings import settings
from app.services.question_limit_service import question_limit_service
from tests.conftest import SITE_A, fake_graph, origin
from tests.test_widget_auth import chat

VISITOR = "v_" + "k" * 30


def session(client, visitor_id=None, ip=None):
    body = {"site_key": SITE_A["key"]}
    if visitor_id is not None:
        body["visitor_id"] = visitor_id
    response = client.post("/api/v1/widget/session", json=body, headers=origin(SITE_A["domain"]))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def claims(token):
    return jwt.get_unverified_claims(token)


# --- Visitor identity ----------------------------------------------------------

def test_session_keeps_the_widgets_visitor_id(client):
    data = session(client, VISITOR)
    assert data["visitor_id"] == VISITOR
    assert claims(data["token"])["vid"] == VISITOR


def test_missing_or_invalid_visitor_id_gets_a_new_one(client):
    seen = set()
    for bad in [None, "", "short", "has spaces in it 12345", "x" * 65, "x" * 256]:
        data = session(client, bad)
        assert data["visitor_id"] != bad
        assert data["visitor_id"].startswith("v_")
        assert claims(data["token"])["vid"] == data["visitor_id"]
        seen.add(data["visitor_id"])
    assert len(seen) == 6  # a fresh id every time


def test_refreshed_token_keeps_visitor_id(client):
    token = session(client, VISITOR)["token"]
    response = client.post("/api/v1/widget/token/refresh",
                           headers={"Authorization": f"Bearer {token}", **origin(SITE_A["domain"])})
    assert claims(response.json()["data"]["token"])["vid"] == VISITOR


# --- Enforcement -----------------------------------------------------------------

def test_limit_reached_returns_429_before_ai_call(client, django_questions):
    django_questions.limits[SITE_A["site_id"]] = 2
    token = session(client, VISITOR)["token"]

    assert chat(client, token).status_code == 200
    assert chat(client, token).status_code == 200
    calls_before = len(fake_graph.calls)

    response = chat(client, token)
    assert response.status_code == 429
    body = response.json()
    assert body["code"] == "question_limit"
    assert body["message"] == "You have used all 2 questions for today."
    assert body["errors"]["limit"] == 2
    assert int(response.headers["Retry-After"]) > 0
    assert len(fake_graph.calls) == calls_before  # no AI call


def test_limit_applies_across_new_sessions_of_same_visitor(client, django_questions):
    django_questions.limits[SITE_A["site_id"]] = 1
    assert chat(client, session(client, VISITOR)["token"]).status_code == 200
    # Page reload: a new session, same stored visitor id.
    assert chat(client, session(client, VISITOR)["token"]).status_code == 429


def test_other_visitors_are_not_affected(client, django_questions):
    django_questions.limits[SITE_A["site_id"]] = 1
    chat(client, session(client, VISITOR)["token"])
    assert chat(client, session(client, "v_" + "z" * 30)["token"]).status_code == 200


def test_django_receives_verified_ids_and_ip_hash_never_raw_ip(client, django_questions):
    token = session(client, VISITOR)["token"]
    chat(client, token, visitor_id="v_" + "e" * 30)  # body values are ignored
    call = django_questions.calls[-1]
    assert call["url"] == "https://django.test/api/internal/chatbot/questions/consume/"
    assert call["auth"] == f"Bearer {settings.DJANGO_SERVICE_API_KEY}"
    assert call["body"]["site_id"] == SITE_A["site_id"]
    assert call["body"]["visitor_id"] == VISITOR
    ip_hash = call["body"]["ip_hash"]
    assert len(ip_hash) == 64 and "testclient" not in ip_hash
    assert ip_hash == question_limit_service.ip_hash("testclient")


def test_failed_reply_is_refunded(client, django_questions):
    django_questions.limits[SITE_A["site_id"]] = 1
    token = session(client, VISITOR)["token"]
    fake_graph.error = RuntimeError("provider down")
    assert chat(client, token).status_code == 502
    assert [c["action"] for c in django_questions.calls] == ["consume", "refund"]

    fake_graph.error = None
    assert chat(client, token).status_code == 200  # the question was given back


def test_refused_requests_do_not_use_questions(client, django_questions, monkeypatch):
    django_questions.limits[SITE_A["site_id"]] = 5
    token = session(client, VISITOR)["token"]
    monkeypatch.setattr(settings, "RATE_LIMIT_CHAT_PER_SESSION", 1)
    chat(client, token)
    assert chat(client, token).status_code == 429  # per-minute rate limit, not the question limit
    assert sum(1 for c in django_questions.calls if c["action"] == "consume") == 1


def test_concurrency_refusal_is_refunded(client, django_questions, monkeypatch):
    django_questions.limits[SITE_A["site_id"]] = 5
    token = session(client, VISITOR)["token"]
    monkeypatch.setattr(settings, "WIDGET_MAX_CONCURRENT_PER_SITE", 1)
    from app.services.rate_limit_service import rate_limit_service
    rate_limit_service.acquire_slot("chat", SITE_A["site_id"], 1)  # another chat in progress
    try:
        assert chat(client, token).status_code == 429
    finally:
        rate_limit_service.release_slot("chat", SITE_A["site_id"])
    assert [c["action"] for c in django_questions.calls] == ["consume", "refund"]


def test_unlimited_site_always_allowed(client, django_questions):
    token = session(client, VISITOR)["token"]
    for _ in range(5):
        assert chat(client, token).status_code == 200


def test_django_unreachable_allows_question(client, django_questions):
    def down(request):
        raise httpx.ConnectError("refused")

    django_questions.override = down
    assert chat(client, session(client, VISITOR)["token"]).status_code == 200


def test_django_error_response_allows_question(client, django_questions):
    django_questions.override = lambda request: httpx.Response(503, json={"error": "service_unavailable"})
    assert chat(client, session(client, VISITOR)["token"]).status_code == 200


def test_questions_url_derived_from_verify_url(monkeypatch):
    monkeypatch.setattr(settings, "DJANGO_QUESTIONS_URL", "")
    monkeypatch.setattr(settings, "DJANGO_SUBSCRIPTION_VERIFY_URL", "http://127.0.0.1:8011/api/internal/chatbot/verify-subscription/")
    assert settings.questions_url == "http://127.0.0.1:8011/api/internal/chatbot/questions/"
    monkeypatch.setattr(settings, "DJANGO_QUESTIONS_URL", "https://admin.example.com/q")
    assert settings.questions_url == "https://admin.example.com/q/"


def test_contact_form_is_not_counted(client, django_questions):
    token = session(client, VISITOR)["token"]
    client.post("/api/v1/contact-us", json={"name": "A", "email": "a@b.com", "country_code": "91", "contact": "9999999999"},
                headers={"Authorization": f"Bearer {token}", **origin(SITE_A["domain"])})
    assert django_questions.calls == []
