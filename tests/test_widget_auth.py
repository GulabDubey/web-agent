import time

import httpx
from jose import jwt
from starlette.routing import WebSocketRoute

from app.config.settings import settings
from app.main import app
from app.services.subscription_service import SubscriptionService
from tests.conftest import (
    django_websites,
    SITE_A,
    SITE_B,
    auth_headers,
    fake_graph,
    fake_redis,
    origin,
    start_session,
)

CHAT = "/api/v1/chat"


def chat(client, token, domain=SITE_A["domain"], message="hello", **extra):
    return client.post(CHAT, json={"message": message, **extra}, headers=auth_headers(token, domain))


def make_token(**overrides):
    now = int(time.time())
    claims = {
        "iss": settings.WIDGET_TOKEN_ISSUER,
        "aud": settings.WIDGET_TOKEN_AUDIENCE,
        "sub": SITE_A["site_id"],
        "cid": SITE_A["customer_id"],
        "sk": SITE_A["key"],
        "dom": SITE_A["domain"],
        "sid": "session-1",
        "iat": now,
        "exp": now + 600,
    }
    secret = overrides.pop("secret", settings.WIDGET_JWT_SECRET)
    claims.update(overrides)
    return jwt.encode(claims, secret, algorithm="HS256")


def clear_auth_cache():
    for key in fake_redis.keys("widget:auth:*"):
        fake_redis.delete(key)


# 1. Valid site key and active subscription -------------------------------------

def test_valid_site_key_issues_token_and_chat_works(client, django):
    response = start_session(client)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["token_type"] == "Bearer"
    assert data["expires_in"] == settings.WIDGET_TOKEN_TTL_SECONDS

    # Django was called server-to-server with the private credential and the
    # domain derived from Origin - never with anything browser-chosen.
    assert django.calls == [{
        "auth": "Bearer test-django-service-key",
        "body": {"site_key": SITE_A["key"], "domain": "companiesnext.com"},
    }]

    claims = jwt.get_unverified_claims(data["token"])
    assert claims["sub"] == SITE_A["site_id"]
    assert claims["aud"] == "chatbot-widget"
    assert claims["exp"] - claims["iat"] == settings.WIDGET_TOKEN_TTL_SECONDS
    assert settings.DJANGO_SERVICE_API_KEY not in response.text
    assert settings.WIDGET_JWT_SECRET not in response.text

    reply = chat(client, data["token"])
    assert reply.status_code == 200, reply.text
    assert reply.json()["data"] == {"message": "answer from companiesnext"}
    assert fake_graph.calls[0]["collection"] == "companiesnext"


def test_www_origin_is_the_same_registered_site(client, django):
    response = start_session(client, domain="www.companiesnext.com")
    assert response.status_code == 200
    assert django.calls[0]["body"]["domain"] == "companiesnext.com"


def test_contact_form_requires_and_uses_widget_session(client, session_token):
    payload = {"name": "Test User", "email": "t@example.com", "country_code": "+91", "contact": "9876543210"}
    response = client.post("/api/v1/contact-us", json=payload, headers=auth_headers(session_token, SITE_A["domain"]))
    assert response.status_code == 200, response.text


# 2. Invalid or revoked site key ------------------------------------------------

def test_unknown_site_key_is_forbidden(client):
    response = client.post(
        "/api/v1/widget/session", json={"site_key": "site_unknownunknownunknown"}, headers=origin("companiesnext.com")
    )
    assert response.status_code == 403
    assert response.json()["code"] == "invalid_site_key"


def test_revoked_site_is_forbidden(client, django):
    django.sites[SITE_A["key"]]["disabled"] = True
    response = start_session(client)
    assert response.status_code == 403
    assert response.json()["code"] == "site_disabled"


def test_malformed_site_key_rejected_without_calling_django(client, django):
    for bad in ["short", "site key with spaces", "x" * 65, "<script>"]:
        response = client.post("/api/v1/widget/session", json={"site_key": bad}, headers=origin("companiesnext.com"))
        assert response.status_code == 400, bad
    response = client.post("/api/v1/widget/session", json={}, headers=origin("companiesnext.com"))
    assert response.status_code == 400
    assert django.calls == []


# 3. Unapproved domain ----------------------------------------------------------

def test_unregistered_domain_is_forbidden(client):
    response = start_session(client, domain="attacker.com")
    assert response.status_code == 403
    assert response.json()["code"] == "domain_not_allowed"


def test_lookalike_and_subdomain_origins_are_forbidden(client):
    for domain in ["companiesnext.com.evil.com", "evilcompaniesnext.com", "shop.companiesnext.com", "companiesnext.co"]:
        response = start_session(client, domain=domain)
        assert response.status_code == 403, domain


def test_static_allowlist_rejects_before_django(client, django, monkeypatch):
    monkeypatch.setattr(settings, "WIDGET_ALLOWED_ORIGINS", "othercustomer.com")
    response = start_session(client)
    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"
    assert django.calls == []


# 4. Forged or missing origin ---------------------------------------------------

def test_missing_or_invalid_origin_is_rejected(client, django):
    for headers in [{}, {"Origin": "null"}, {"Origin": "https://companiesnext.com/path"},
                    {"Origin": "ftp://companiesnext.com"}, {"Origin": "https://user@companiesnext.com"},
                    {"Origin": "not a url"}, {"Origin": "https://companiesnext.com:abc"}]:
        response = client.post("/api/v1/widget/session", json={"site_key": SITE_A["key"]}, headers=headers)
        assert response.status_code == 403, headers
    assert django.calls == []


def test_plain_http_and_localhost_rejected_outside_development(client, django):
    assert start_session(client, scheme="http").status_code == 403
    assert start_session(client, domain="localhost:5000", scheme="http").status_code == 403
    assert start_session(client, domain="127.0.0.1:5000", scheme="http").status_code == 403
    assert django.calls == []


def test_localhost_verified_as_its_own_host_and_port_in_development(client, django, monkeypatch):
    # A site registered in Django (DEBUG on) as "127.0.0.1:8012".
    monkeypatch.setattr(settings, "APP_ENV", "development")
    django.sites[SITE_A["key"]]["domain"] = "127.0.0.1:8012"

    response = start_session(client, domain="127.0.0.1:8012", scheme="http")
    assert response.status_code == 200
    assert django.calls[-1]["body"]["domain"] == "127.0.0.1:8012"

    # Another local port is a different site.
    response = start_session(client, domain="127.0.0.1:8000", scheme="http")
    assert response.status_code == 403
    assert response.json()["code"] == "domain_not_allowed"
    assert django.calls[-1]["body"]["domain"] == "127.0.0.1:8000"


def test_other_local_hosts_keep_their_port_in_development(client, django, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    start_session(client, domain="localhost:3000", scheme="http")
    assert django.calls[-1]["body"]["domain"] == "localhost:3000"
    start_session(client, domain="[::1]:8012", scheme="http")
    assert django.calls[-1]["body"]["domain"] == "[::1]:8012"


def test_dev_domain_overrides_local_origin_in_development(client, django, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "WIDGET_DEV_DOMAIN", "companiesnext.com")
    response = start_session(client, domain="127.0.0.1:5000", scheme="http")
    assert response.status_code == 200
    assert django.calls[-1]["body"]["domain"] == "companiesnext.com"


def test_local_session_token_is_bound_to_its_port(client, django, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    django.sites[SITE_A["key"]]["domain"] = "127.0.0.1:8012"
    token = start_session(client, domain="127.0.0.1:8012", scheme="http").json()["data"]["token"]

    other_port = {"Authorization": f"Bearer {token}", "Origin": "http://127.0.0.1:9999"}
    response = client.post(CHAT, json={"message": "hi"}, headers=other_port)
    assert response.status_code == 403
    assert response.json()["code"] == "origin_not_allowed"


def test_token_used_from_a_different_origin_is_rejected(client, session_token):
    response = chat(client, session_token, domain="attacker.com")
    assert response.status_code == 403
    response = client.post(CHAT, json={"message": "hi"}, headers={"Authorization": f"Bearer {session_token}"})
    assert response.status_code == 403
    assert fake_graph.calls == []


# 5. Django rejects expired or unpaid subscriptions -----------------------------

def test_expired_subscription_is_forbidden(client, django):
    django.sites[SITE_A["key"]]["subscription"] = "expired"
    response = start_session(client)
    assert response.status_code == 403
    assert response.json()["code"] == "subscription_expired"


def test_unpaid_subscription_is_forbidden(client, django):
    django.sites[SITE_A["key"]]["subscription"] = "inactive"
    response = start_session(client)
    assert response.status_code == 403
    assert response.json()["code"] == "subscription_inactive"


# 6. Django unavailable -> fail closed ------------------------------------------

def test_django_network_errors_fail_closed(client, django):
    def boom(request):
        raise httpx.ConnectError("refused")

    django.override = boom
    response = start_session(client)
    assert response.status_code == 503
    assert response.json()["code"] == "verification_unavailable"

    def slow(request):
        raise httpx.ReadTimeout("timeout")

    django.override = slow
    assert start_session(client).status_code == 503


def test_django_server_errors_and_bad_credential_fail_closed(client, django):
    for status in (500, 502, 503, 401, 429):
        django.override = lambda request, status=status: httpx.Response(status, json={"error": "x"})
        response = start_session(client)
        assert response.status_code == 503, status
        assert "x" != response.json()["message"]


def test_repeated_django_failures_open_the_circuit(client, django):
    django.override = lambda request: httpx.Response(500)
    for _ in range(settings.DJANGO_VERIFY_FAILURE_THRESHOLD):
        start_session(client)
    calls = len(django.calls)

    django.override = None  # Django recovered, but the cooldown still applies
    assert start_session(client).status_code == 503
    assert len(django.calls) == calls


def test_missing_django_configuration_fails_closed(client, django, monkeypatch):
    monkeypatch.setattr(settings, "DJANGO_SERVICE_API_KEY", "")
    assert start_session(client).status_code == 503
    monkeypatch.setattr(settings, "DJANGO_SERVICE_API_KEY", "k")
    monkeypatch.setattr(settings, "DJANGO_SUBSCRIPTION_VERIFY_URL", "http://django.test/verify/")
    assert start_session(client).status_code == 503  # https required outside development
    assert django.calls == []


# 7. Malformed Django responses -------------------------------------------------

def test_malformed_django_responses_are_rejected(client, django):
    bad_responses = [
        httpx.Response(200, text="<html>ok</html>"),
        httpx.Response(200, json=["authorized"]),
        httpx.Response(200, json={"authorized": "true", "site_id": "11", "customer_id": "1",
                                  "expires_at": "2099-01-01T00:00:00Z"}),
        httpx.Response(200, json={"authorized": True, "customer_id": "1", "expires_at": "2099-01-01T00:00:00Z"}),
        httpx.Response(200, json={"authorized": True, "site_id": "11", "customer_id": "1", "expires_at": "garbage"}),
        httpx.Response(200, json={"authorized": True, "site_id": "11", "customer_id": "1",
                                  "expires_at": "2000-01-01T00:00:00Z"}),
        httpx.Response(403, text="Forbidden"),
    ]
    for bad in bad_responses:
        django.override = lambda request, bad=bad: bad
        response = start_session(client)
        assert response.status_code in (502, 503), bad.content
        assert "token" not in (response.json().get("data") or {})
        fake_redis.delete("widget:django:circuit_open", "widget:django:failures")


# 8. Missing or expired widget token --------------------------------------------

def test_missing_token_is_unauthorized(client):
    response = client.post(CHAT, json={"message": "hi"}, headers=origin(SITE_A["domain"]))
    assert response.status_code == 401
    assert response.json()["code"] == "token_missing"


def test_expired_token_is_unauthorized_but_refreshable(client):
    now = int(time.time())
    expired = make_token(iat=now - 700, exp=now - 100)
    response = chat(client, expired)
    assert response.status_code == 401
    assert response.json()["code"] == "token_expired"

    refreshed = client.post("/api/v1/widget/token/refresh", headers=auth_headers(expired, SITE_A["domain"]))
    assert refreshed.status_code == 200, refreshed.text
    new_token = refreshed.json()["data"]["token"]
    assert jwt.get_unverified_claims(new_token)["sid"] == "session-1"  # same chat session
    assert chat(client, new_token).status_code == 200


def test_refresh_requires_exp_claim(client):
    token = jwt.encode(
        {k: v for k, v in jwt.get_unverified_claims(make_token()).items() if k != "exp"},
        settings.WIDGET_JWT_SECRET, algorithm="HS256",
    )
    response = client.post("/api/v1/widget/token/refresh", headers=auth_headers(token, SITE_A["domain"]))
    assert response.status_code == 401


def test_token_past_refresh_grace_cannot_be_refreshed(client):
    now = int(time.time())
    stale = make_token(iat=now - 10_000, exp=now - settings.WIDGET_TOKEN_REFRESH_GRACE_SECONDS - 10)
    response = client.post("/api/v1/widget/token/refresh", headers=auth_headers(stale, SITE_A["domain"]))
    assert response.status_code == 401


def test_refresh_rechecks_subscription(client, django, session_token):
    django.sites[SITE_A["key"]]["subscription"] = "expired"
    clear_auth_cache()
    response = client.post("/api/v1/widget/token/refresh", headers=auth_headers(session_token, SITE_A["domain"]))
    assert response.status_code == 403


# 9. Incorrect JWT signature, audience, issuer or algorithm ---------------------

def test_tampered_tokens_are_rejected(client):
    bad_tokens = [
        make_token(secret="a-completely-different-secret-value-123456"),
        make_token(aud="another-audience"),
        make_token(iss="someone-else"),
        jwt.encode({"sub": "11"}, settings.WIDGET_JWT_SECRET, algorithm="HS256"),  # missing claims
        "not.a.jwt",
    ]
    # Unsigned "alg: none" token claiming to be site A.
    import base64, json as _json
    def b64(obj):
        return base64.urlsafe_b64encode(_json.dumps(obj).encode()).rstrip(b"=").decode()
    claims = jwt.get_unverified_claims(make_token())
    bad_tokens.append(f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}.")

    for token in bad_tokens:
        response = chat(client, token)
        assert response.status_code == 401, token
    assert fake_graph.calls == []


def test_weak_or_reused_signing_secret_disables_tokens(client, monkeypatch):
    monkeypatch.setattr(settings, "WIDGET_JWT_SECRET", "short")
    assert start_session(client).status_code == 503
    monkeypatch.setattr(settings, "WIDGET_JWT_SECRET", "x" * 40)
    monkeypatch.setattr(settings, "DJANGO_SERVICE_API_KEY", "x" * 40)
    assert start_session(client).status_code == 503


# 10. Direct API calls without authorization ------------------------------------

def test_direct_api_calls_without_auth_are_rejected(client):
    assert client.post(CHAT, json={"session_id": "x", "message": "hi"}).status_code == 401
    assert client.post("/api/v1/contact-us", json={
        "session_id": "x", "name": "Test", "email": "t@example.com", "country_code": "+91", "contact": "9876543210",
    }).status_code == 401
    assert fake_graph.calls == []


def test_internal_endpoints_require_service_token(client, monkeypatch):
    requests = [
        ("get", "/api/v1/users", None),
        ("get", "/api/v1/users/1", None),
        ("post", "/api/v1/internal/widget/invalidate", {"site_key": SITE_A["key"]}),
    ]
    for method, path, body in requests:
        assert client.request(method, path, json=body).status_code == 401, path
        response = client.request(method, path, json=body, headers={"Authorization": "Bearer wrong"})
        assert response.status_code == 401, path

    # A widget token is not a service token.
    widget_token = make_token()
    response = client.post("/api/v1/internal/widget/invalidate", json={"site_key": SITE_A["key"]},
                           headers={"Authorization": f"Bearer {widget_token}"})
    assert response.status_code == 401

    monkeypatch.setattr(settings, "INTERNAL_SERVICE_TOKENS", "")
    assert client.get("/api/v1/users").status_code == 503


# 11. Cross-customer isolation --------------------------------------------------

def test_sites_get_their_own_knowledge_and_history(client):
    token_a = start_session(client).json()["data"]["token"]
    token_b = start_session(client, site=SITE_B).json()["data"]["token"]

    assert chat(client, token_a).json()["data"]["message"] == "answer from companiesnext"
    assert chat(client, token_b, domain=SITE_B["domain"]).json()["data"]["message"] == "answer from othercustomer_kb"

    sid_a = jwt.get_unverified_claims(token_a)["sid"]
    sid_b = jwt.get_unverified_claims(token_b)["sid"]
    history = fake_redis.keys("chat:session:*")
    assert f"chat:session:{SITE_A['site_id']}:{sid_a}" in history
    assert f"chat:session:{SITE_B['site_id']}:{sid_b}" in history


def test_session_id_in_body_cannot_select_another_session(client):
    token_a = start_session(client).json()["data"]["token"]
    token_b = start_session(client, site=SITE_B).json()["data"]["token"]
    sid_b = jwt.get_unverified_claims(token_b)["sid"]

    chat(client, token_a, session_id=sid_b)
    assert fake_redis.keys(f"chat:session:{SITE_B['site_id']}:*") == []


def test_token_for_one_site_cannot_be_used_for_another(client):
    token_a = start_session(client).json()["data"]["token"]
    assert chat(client, token_a, domain=SITE_B["domain"]).status_code == 403

    # Even a validly signed token claiming site B's id with site A's key is refused.
    forged = make_token(sub=SITE_B["site_id"], cid=SITE_B["customer_id"])
    assert chat(client, forged).status_code == 401
    assert all(call["collection"] == "companiesnext" for call in fake_graph.calls)


# 12. Subscription cancelled after a session was issued -------------------------

def test_cancellation_applies_after_cache_ttl(client, django, session_token):
    assert chat(client, session_token).status_code == 200
    django.sites[SITE_A["key"]]["subscription"] = "expired"

    clear_auth_cache()  # what the short WIDGET_AUTH_CACHE_TTL_SECONDS expiry does
    response = chat(client, session_token)
    assert response.status_code == 403
    assert response.json()["code"] == "subscription_expired"
    assert len(fake_graph.calls) == 1


def test_invalidate_endpoint_applies_cancellation_immediately(client, django, session_token):
    assert chat(client, session_token).status_code == 200
    django.sites[SITE_A["key"]]["subscription"] = "expired"

    response = client.post("/api/v1/internal/widget/invalidate", json={"site_key": SITE_A["key"]},
                           headers={"Authorization": "Bearer test-internal-token"})
    assert response.status_code == 200
    assert chat(client, session_token).status_code == 403


def test_authorization_is_cached_briefly(client, django, session_token):
    calls = len(django.calls)
    for _ in range(3):
        assert chat(client, session_token).status_code == 200
    assert len(django.calls) == calls


def test_django_outage_with_expired_cache_fails_closed(client, django, session_token):
    clear_auth_cache()
    django.override = lambda request: httpx.Response(503)
    assert chat(client, session_token).status_code == 503
    assert fake_graph.calls == []


def test_cache_never_outlives_subscription_expiry(monkeypatch):
    service = SubscriptionService(redis=fake_redis)
    stored = {}
    monkeypatch.setattr(service, "_store", lambda site_key, domain, entry, ttl: stored.update(ttl=ttl))

    async def verify(site_key, domain):
        from app.services.subscription_service import SiteAuthorization
        return SiteAuthorization("11", "101", domain, "Pro", time.time() + 5)

    monkeypatch.setattr(service, "_verify_with_django", verify)
    import asyncio
    asyncio.run(service.authorize(SITE_A["key"], SITE_A["domain"]))
    assert stored["ttl"] <= 5


# 13. Rate limiting and usage control -------------------------------------------

def test_chat_rate_limit_per_session(client, session_token, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_CHAT_PER_SESSION", 2)
    assert chat(client, session_token).status_code == 200
    assert chat(client, session_token).status_code == 200
    response = chat(client, session_token)
    assert response.status_code == 429
    assert "Retry-After" in response.headers
    assert len(fake_graph.calls) == 2


def test_invalid_site_key_attempts_are_rate_limited(client, django, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_INVALID_KEY_PER_IP", 3)
    for i in range(3):
        client.post("/api/v1/widget/session", json={"site_key": f"site_guess_{i:08d}"}, headers=origin("companiesnext.com"))
    calls = len(django.calls)

    # Blocked even for a valid key, without reaching Django.
    assert start_session(client).status_code == 429
    assert len(django.calls) == calls


def test_session_creation_rate_limit(client, monkeypatch):
    monkeypatch.setattr(settings, "RATE_LIMIT_SESSIONS_PER_IP", 2)
    assert start_session(client).status_code == 200
    assert start_session(client).status_code == 200
    assert start_session(client).status_code == 429


def test_concurrent_chat_limit_per_site(client, session_token, monkeypatch):
    monkeypatch.setattr(settings, "WIDGET_MAX_CONCURRENT_PER_SITE", 1)
    fake_redis.set(f"conc:chat:{SITE_A['site_id']}", 1)  # one chat already in flight
    assert chat(client, session_token).status_code == 429
    fake_redis.set(f"conc:chat:{SITE_A['site_id']}", 0)
    assert chat(client, session_token).status_code == 200
    assert fake_redis.get(f"conc:chat:{SITE_A['site_id']}") == "0"  # slot released


def test_daily_token_budget_per_site(client, session_token, monkeypatch):
    monkeypatch.setattr(settings, "WIDGET_DAILY_TOKEN_LIMIT_PER_SITE", 10)
    assert chat(client, session_token, message="x" * 100).status_code == 200  # records ~30 tokens
    response = chat(client, session_token)
    assert response.status_code == 429
    assert response.json()["code"] == "usage_limit"


def test_oversized_message_rejected_before_ai(client, session_token):
    response = chat(client, session_token, message="x" * (settings.WIDGET_MAX_MESSAGE_CHARS + 1))
    assert response.status_code == 400
    assert fake_graph.calls == []


# 14. Streaming / WebSocket endpoints -------------------------------------------

def test_no_unprotected_websocket_routes_exist():
    # The app has no streaming or WebSocket endpoints today; if one is
    # added it must get widget auth (and a test) before this is updated.
    assert not [route for route in app.router.routes if isinstance(route, WebSocketRoute)]


# CORS is scoped to widget endpoints ---------------------------------------------

def test_cors_only_on_widget_endpoints(client):
    preflight = {"Origin": "https://companiesnext.com", "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization,content-type"}
    response = client.options(CHAT, headers=preflight)
    assert response.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in response.headers

    response = client.options("/api/v1/users", headers=preflight)
    assert "access-control-allow-origin" not in response.headers


# Knowledge collection comes from Django's websites table -----------------------

def test_chat_reads_collection_name_from_django_on_every_message(client, session_token):
    assert chat(client, session_token).json()["data"]["message"] == "answer from companiesnext"

    django_websites[SITE_A["site_id"]]["collection_name"] = "FlaskshopV2"  # changed in admin
    assert chat(client, session_token).json()["data"]["message"] == "answer from FlaskshopV2"


def test_site_without_collection_name_is_refused_before_ai(client, session_token):
    for value in ("", None, "bad name; DROP TABLE", "x" * 101):
        django_websites[SITE_A["site_id"]]["collection_name"] = value
        response = chat(client, session_token)
        assert response.status_code == 403, value
        assert response.json()["code"] == "no_knowledge_base"
    assert fake_graph.calls == []


def test_missing_or_inactive_site_row_is_refused(client, session_token):
    django_websites[SITE_A["site_id"]]["is_active"] = 0
    assert chat(client, session_token).json()["code"] == "site_disabled"
    del django_websites[SITE_A["site_id"]]
    assert chat(client, session_token).status_code == 403
    assert fake_graph.calls == []


def test_django_database_error_fails_closed(client, session_token):
    django_websites[SITE_A["site_id"]] = ConnectionError("mysql down")
    response = chat(client, session_token)
    assert response.status_code == 503
    assert "mysql" not in response.text
    assert fake_graph.calls == []


# Model replies are returned as plain text ----------------------------------------

def test_answer_text_keeps_only_text_blocks():
    from app.services.chat_service import ChatService

    blocks = [
        {"type": "thinking", "thinking": "secret reasoning", "signature": "abc"},
        {"type": "text", "text": "- First point"},
        {"type": "text", "text": "Second part"},
    ]
    assert ChatService.answer_text(blocks) == "- First point\n\nSecond part"
    assert ChatService.answer_text("  plain  ") == "plain"
    assert ChatService.answer_text(None) == ""


def test_chat_never_returns_thinking_blocks(client, session_token, monkeypatch):
    def invoke(state):
        return {**state, "answer": [{"type": "thinking", "thinking": "hidden", "signature": "sig"},
                                    {"type": "text", "text": "Visible answer"}], "meta_data": None}

    monkeypatch.setattr(fake_graph, "invoke", invoke)
    response = chat(client, session_token)
    assert response.json()["data"] == {"message": "Visible answer"}
    assert "hidden" not in response.text and "sig" not in response.text


def test_empty_answer_gets_friendly_fallback(client, session_token, monkeypatch):
    monkeypatch.setattr(fake_graph, "invoke", lambda state: {**state, "answer": [], "meta_data": None})
    message = chat(client, session_token).json()["data"]["message"]
    assert isinstance(message, str) and message


def test_contact_form_accepts_international_numbers(client, session_token):
    payload = {"name": "Test User", "email": "t@example.com", "country_code": "+44", "contact": "7911123456"}
    headers = auth_headers(session_token, SITE_A["domain"])
    assert client.post("/api/v1/contact-us", json=payload, headers=headers).status_code == 200
    payload.update(country_code="+91", contact="12345")
    assert client.post("/api/v1/contact-us", json=payload, headers=headers).status_code == 400
