import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime

import httpx

from app.config.redis import RedisClient
from app.config.settings import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# Public messages for Django's denial reasons; anything unknown is generic.
DENIAL_MESSAGES = {
    "invalid_site_key": "Invalid site key.",
    "site_disabled": "This website's chatbot is disabled.",
    "domain_not_allowed": "This domain is not authorized for this site key.",
    "subscription_inactive": "This website does not have an active subscription.",
    "subscription_expired": "This website's subscription has expired.",
}


@dataclass(frozen=True)
class SiteAuthorization:
    site_id: str
    customer_id: str
    domain: str
    plan: str
    expires_at: float  # unix time the subscription ends


def denied(reason):
    return AppException(
        DENIAL_MESSAGES.get(reason, "This website is not authorized to use the chatbot."),
        403,
        code=reason if reason in DENIAL_MESSAGES else "not_authorized",
    )


def unavailable():
    return AppException(
        "Chatbot authorization is temporarily unavailable. Please try again shortly.",
        503,
        code="verification_unavailable",
    )


class SubscriptionService:
    """
    Asks the Django project (source of truth for payments) whether a site
    key may be used on a domain. Answers are cached briefly in Redis; any
    failure to get a clear answer fails closed.
    """

    FAILURES_KEY = "widget:django:failures"
    CIRCUIT_KEY = "widget:django:circuit_open"

    def __init__(self, redis=None, transport=None):
        self._redis = redis
        self._transport = transport
        self._client = None

    @property
    def redis(self):
        return self._redis or RedisClient().client

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

    @staticmethod
    def cache_key(site_key):
        return "widget:auth:" + hashlib.sha256(site_key.encode()).hexdigest()

    def invalidate(self, site_key):
        try:
            self.redis.delete(self.cache_key(site_key))
        except Exception:
            logger.exception("Failed to invalidate cached site authorization")

    # --- cache ---------------------------------------------------------------

    def _cached(self, site_key, domain):
        try:
            raw = self.redis.get(self.cache_key(site_key))
            entry = json.loads(raw) if raw else None
        except Exception:
            logger.warning("Authorization cache unavailable; verifying with Django")
            return None

        if not isinstance(entry, dict) or entry.get("domain") != domain:
            return None
        if entry.get("authorized") is False:
            raise denied(entry.get("reason"))

        auth = entry.get("auth") or {}
        if auth.get("expires_at", 0) <= time.time():
            return None
        return SiteAuthorization(**auth)

    def _store(self, site_key, domain, entry, ttl):
        if ttl <= 0:
            return
        try:
            self.redis.set(self.cache_key(site_key), json.dumps({"domain": domain, **entry}), ex=int(ttl))
        except Exception:
            logger.warning("Failed to cache site authorization")

    # --- circuit breaker -----------------------------------------------------

    def _circuit_open(self):
        try:
            return bool(self.redis.get(self.CIRCUIT_KEY))
        except Exception:
            return False

    def _record_failure(self):
        try:
            failures = self.redis.incr(self.FAILURES_KEY)
            if failures == 1:
                self.redis.expire(self.FAILURES_KEY, 60)
            if failures >= settings.DJANGO_VERIFY_FAILURE_THRESHOLD:
                self.redis.set(self.CIRCUIT_KEY, "1", ex=settings.DJANGO_VERIFY_COOLDOWN_SECONDS)
                self.redis.delete(self.FAILURES_KEY)
                logger.error(
                    "Django verification failing repeatedly; pausing calls for %ss",
                    settings.DJANGO_VERIFY_COOLDOWN_SECONDS,
                )
        except Exception:
            pass

    # --- verification --------------------------------------------------------

    async def authorize(self, site_key, domain):
        """Return SiteAuthorization or raise 403/503 (never grants on doubt)."""
        cached = self._cached(site_key, domain)
        if cached:
            return cached

        if self._circuit_open():
            raise unavailable()

        auth = await self._verify_with_django(site_key, domain)

        ttl = min(settings.WIDGET_AUTH_CACHE_TTL_SECONDS, auth.expires_at - time.time())
        self._store(site_key, domain, {"authorized": True, "auth": asdict(auth)}, ttl)
        return auth

    async def _verify_with_django(self, site_key, domain):
        url = settings.DJANGO_SUBSCRIPTION_VERIFY_URL
        api_key = settings.DJANGO_SERVICE_API_KEY
        if not url or not api_key or (not settings.is_development and not url.startswith("https://")):
            logger.error("Django verification is not configured (URL must be https outside development)")
            raise unavailable()

        try:
            response = await self._http().post(
                url,
                json={"site_key": site_key, "domain": domain},
                headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            )
        except httpx.HTTPError as error:
            logger.warning("Django verification request failed: %s", type(error).__name__)
            self._record_failure()
            raise unavailable()

        try:
            data = response.json()
        except ValueError:
            data = None

        if response.status_code == 403 and isinstance(data, dict) and data.get("authorized") is False:
            reason = data.get("reason") if isinstance(data.get("reason"), str) else "not_authorized"
            logger.info("Django denied site key %s… on %s: %s", site_key[:10], domain, reason)
            self._store(site_key, domain, {"authorized": False, "reason": reason}, settings.WIDGET_DENY_CACHE_TTL_SECONDS)
            raise denied(reason)

        if response.status_code == 400:
            raise AppException("Malformed site key or domain.", 400, code="invalid_request")

        if response.status_code != 200:
            if response.status_code == 401:
                logger.error("Django rejected DJANGO_SERVICE_API_KEY (HTTP 401)")
            else:
                logger.warning("Django verification returned HTTP %s", response.status_code)
            self._record_failure()
            raise unavailable()

        auth = self._parse_authorized(data, domain)
        if auth is None:
            logger.error("Django verification returned a malformed response")
            self._record_failure()
            raise AppException(
                "Chatbot authorization returned an invalid response.", 502, code="verification_invalid"
            )
        return auth

    @staticmethod
    def _parse_authorized(data, domain):
        if not isinstance(data, dict) or data.get("authorized") is not True:
            return None

        site_id, customer_id = data.get("site_id"), data.get("customer_id")
        if not isinstance(site_id, str) or not site_id or not isinstance(customer_id, str) or not customer_id:
            return None

        try:
            expires_at = datetime.fromisoformat(str(data.get("expires_at")).replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
        if expires_at <= time.time():
            return None

        plan = data.get("plan") if isinstance(data.get("plan"), str) else ""
        return SiteAuthorization(site_id, customer_id, domain, plan, expires_at)


subscription_service = SubscriptionService()
