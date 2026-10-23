import logging
import time

import httpx

from app.config.settings import settings
from app.llm.factory import LLMConfig, env_llm_config, get_chat_model

logger = logging.getLogger(__name__)

API_TYPES = {"anthropic", "openai"}


class LLMConfigService:
    """
    Which LLM answers a website's chat: the website's active provider and
    model, configured in Django (Admin → Websites → AI model).

    - Cached per site in process memory for LLM_CONFIG_CACHE_TTL_SECONDS.
    - The website has no active provider (404 llm_not_configured) → this
      service's own .env Anthropic settings, so chat keeps working before setup.
    - Django unreachable → the last config it returned for the site, or
      the .env settings if there is none.
    """

    def __init__(self, transport=None):
        self._transport = transport
        self._client = None
        self._cache: dict[str, tuple[float, LLMConfig]] = {}

    def _http(self):
        if self._client is None:
            timeout = settings.DJANGO_VERIFY_TIMEOUT_SECONDS
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=min(timeout, 3.0)),
                follow_redirects=False,
                transport=self._transport,
            )
        return self._client

    async def aclose(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def clear(self, site_id=None):
        if site_id is None:
            self._cache.clear()
        else:
            self._cache.pop(str(site_id), None)

    async def config_for(self, site_id) -> LLMConfig:
        site_id = str(site_id)
        cached = self._cache.get(site_id)
        if cached and cached[0] > time.monotonic():
            return cached[1]

        stale = cached[1] if cached else None
        config = await self._fetch(site_id, stale)
        self._cache[site_id] = (time.monotonic() + settings.LLM_CONFIG_CACHE_TTL_SECONDS, config)
        return config

    async def model_for(self, site_id):
        config = await self.config_for(site_id)
        return get_chat_model(config), config

    async def _fetch(self, site_id, stale):
        url, api_key = settings.llm_config_url, settings.DJANGO_SERVICE_API_KEY
        if not url or not api_key:
            return env_llm_config()

        try:
            response = await self._http().post(
                url,
                json={"site_id": site_id},
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Could not fetch LLM config for site %s: %s", site_id, type(error).__name__)
            return stale or env_llm_config()

        if response.status_code == 404 and isinstance(data, dict) and data.get("error") == "llm_not_configured":
            return env_llm_config()

        config = self._parse(data) if response.status_code == 200 else None
        if config is None:
            logger.warning("Django LLM config for site %s unusable (HTTP %s)", site_id, response.status_code)
            return stale or env_llm_config()

        logger.info("Site %s uses %s · %s (%s)", site_id, config.provider, config.model, config.source)
        return config

    @staticmethod
    def _parse(data):
        if not isinstance(data, dict):
            return None
        api_type, model, key = data.get("api_type"), data.get("model"), data.get("api_key")
        base_url = data.get("base_url") or ""
        if api_type not in API_TYPES or not isinstance(model, str) or not model:
            return None
        if not isinstance(key, str) or not key or not isinstance(base_url, str):
            return None
        return LLMConfig(
            api_type=api_type,
            model=model,
            api_key=key,
            base_url=base_url,
            provider=str(data.get("provider") or ""),
            source=str(data.get("source") or "default"),
        )


llm_config_service = LLMConfigService()
