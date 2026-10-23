"""Per-website LLM provider/model chosen in Django and used by the chat API."""

import httpx
import pytest
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.llm import factory
from app.llm.factory import LLMConfig, UnsupportedProvider, get_chat_model
from app.services.llm_config_service import llm_config_service
from tests.conftest import SITE_A, fake_graph
from tests.test_widget_auth import chat

GROQ = {
    "provider": "Groq", "provider_id": "2", "api_type": "openai",
    "base_url": "https://api.groq.com/openai/v1", "model": "llama-3.3-70b-versatile",
    "api_key": "gsk-test-key", "source": "website",
}
CLAUDE = {
    "provider": "Anthropic", "provider_id": "1", "api_type": "anthropic", "base_url": "",
    "model": "claude-haiku-4-5", "api_key": "sk-ant-test", "source": "default",
}


def llm_used():
    return fake_graph.calls[-1]["llm"]


# --- Chat uses the site's configured provider ----------------------------------

def test_chat_uses_openai_compatible_provider_chosen_for_site(client, session_token, django_llm):
    django_llm.configs[SITE_A["site_id"]] = GROQ

    assert chat(client, session_token).status_code == 200

    llm = llm_used()
    assert isinstance(llm, ChatOpenAI)
    assert llm.model_name == "llama-3.3-70b-versatile"
    assert str(llm.openai_api_base) == "https://api.groq.com/openai/v1"
    assert llm.openai_api_key.get_secret_value() == "gsk-test-key"


def test_chat_uses_default_anthropic_provider(client, session_token, django_llm):
    django_llm.configs[SITE_A["site_id"]] = CLAUDE
    chat(client, session_token)
    llm = llm_used()
    assert isinstance(llm, ChatAnthropic)
    assert llm.model == "claude-haiku-4-5"


def test_django_called_with_service_key_and_verified_site_id(client, session_token, django_llm):
    django_llm.configs[SITE_A["site_id"]] = GROQ
    # A site_id in the request body must be ignored; only the token's site counts.
    chat(client, session_token, site_id="22")
    call = django_llm.calls[-1]
    assert call["body"] == {"site_id": SITE_A["site_id"]}
    assert call["auth"] == f"Bearer {settings.DJANGO_SERVICE_API_KEY}"
    assert call["url"] == "https://django.test/api/internal/chatbot/llm-config/"


def test_not_configured_in_django_falls_back_to_env(client, session_token, django_llm):
    chat(client, session_token)
    llm = llm_used()
    assert isinstance(llm, ChatAnthropic)
    assert llm.model == settings.ANTHROPIC_MODEL


def test_config_is_cached_then_refetched_after_ttl(client, session_token, django_llm, monkeypatch):
    django_llm.configs[SITE_A["site_id"]] = GROQ
    chat(client, session_token)
    chat(client, session_token)
    assert len(django_llm.calls) == 1

    monkeypatch.setattr(settings, "LLM_CONFIG_CACHE_TTL_SECONDS", 0)
    llm_config_service.clear()
    django_llm.configs[SITE_A["site_id"]] = CLAUDE  # admin switched provider
    chat(client, session_token)
    assert isinstance(llm_used(), ChatAnthropic)


def test_django_outage_reuses_last_known_config(client, session_token, django_llm, monkeypatch):
    monkeypatch.setattr(settings, "LLM_CONFIG_CACHE_TTL_SECONDS", 0)
    django_llm.configs[SITE_A["site_id"]] = GROQ
    chat(client, session_token)

    def down(request):
        raise httpx.ConnectError("refused")

    django_llm.override = down
    assert chat(client, session_token).status_code == 200
    assert isinstance(llm_used(), ChatOpenAI)


def test_django_outage_without_history_uses_env(client, session_token, django_llm):
    django_llm.override = lambda request: httpx.Response(503, json={"error": "service_unavailable"})
    assert chat(client, session_token).status_code == 200
    assert isinstance(llm_used(), ChatAnthropic)


@pytest.mark.parametrize("bad", [
    {**GROQ, "api_type": "cohere"},
    {**GROQ, "model": ""},
    {**GROQ, "api_key": None},
    {**GROQ, "base_url": 5},
    ["not", "a", "dict"],
])
def test_malformed_config_is_not_used(client, session_token, django_llm, bad):
    django_llm.override = lambda request: httpx.Response(200, json=bad)
    chat(client, session_token)
    assert isinstance(llm_used(), ChatAnthropic)
    assert llm_used().model == settings.ANTHROPIC_MODEL


def test_api_key_never_returned_to_browser(client, session_token, django_llm):
    django_llm.configs[SITE_A["site_id"]] = GROQ
    response = chat(client, session_token)
    assert "gsk-test-key" not in response.text
    assert "llama" not in response.text


def test_provider_failure_is_a_clean_502(client, session_token, django_llm):
    django_llm.configs[SITE_A["site_id"]] = GROQ
    fake_graph.error = RuntimeError("401 invalid api key gsk-test-key")
    response = chat(client, session_token)
    assert response.status_code == 502
    assert response.json()["code"] == "llm_unavailable"
    assert "gsk-test-key" not in response.text


def test_invalidate_clears_llm_cache(client, session_token, django_llm):
    django_llm.configs[SITE_A["site_id"]] = GROQ
    chat(client, session_token)
    client.post(
        "/api/v1/internal/widget/invalidate",
        json={"site_key": SITE_A["key"]},
        headers={"Authorization": "Bearer test-internal-token"},
    )
    chat(client, session_token)
    assert len(django_llm.calls) == 2


# --- Factory -----------------------------------------------------------------

def test_factory_caches_by_provider_model_and_key():
    a = get_chat_model(LLMConfig("openai", "gpt-4o-mini", "k1"))
    assert get_chat_model(LLMConfig("openai", "gpt-4o-mini", "k1")) is a
    assert get_chat_model(LLMConfig("openai", "gpt-4o-mini", "k2")) is not a
    assert get_chat_model(LLMConfig("openai", "gpt-4o", "k1")) is not a


def test_factory_rejects_unknown_api_type():
    with pytest.raises(UnsupportedProvider):
        get_chat_model(LLMConfig("cohere", "command-r", "k"))


def test_api_key_hidden_from_config_repr():
    assert "secret-key" not in repr(LLMConfig("openai", "gpt-4o", "secret-key"))


def test_llm_config_url_derived_from_verify_url(monkeypatch):
    monkeypatch.setattr(settings, "DJANGO_LLM_CONFIG_URL", "")
    monkeypatch.setattr(settings, "DJANGO_SUBSCRIPTION_VERIFY_URL", "http://127.0.0.1:8011/api/internal/chatbot/verify-subscription/")
    assert settings.llm_config_url == "http://127.0.0.1:8011/api/internal/chatbot/llm-config/"
    monkeypatch.setattr(settings, "DJANGO_LLM_CONFIG_URL", "https://admin.example.com/llm/")
    assert settings.llm_config_url == "https://admin.example.com/llm/"
