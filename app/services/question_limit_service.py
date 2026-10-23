import hashlib
import hmac
import logging
from datetime import datetime, timezone

import httpx

from app.config.settings import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

DEFAULT_MESSAGE = "You've reached the question limit for this chat. Please try again later."


class QuestionLimitService:
    """
    Per-visitor question limit set on each website in the Django admin.

    Django keeps the counters (in MySQL, shared by every worker and kept
    across restarts). Each chat question is consumed before the AI call and
    refunded if the reply fails. Only a keyed hash of the visitor's IP is
    sent, never the IP itself.

    If Django can't be reached the question is allowed (logged): a limit
    is a usage cap, and an outage shouldn't take every chatbot down.
    """

    def __init__(self, transport=None):
        self._transport = transport
        self._client = None

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
    def ip_hash(ip):
        if not ip or ip == "unknown":
            return ""
        return hmac.new(settings.WIDGET_JWT_SECRET.encode(), ip.encode(), hashlib.sha256).hexdigest()

    async def _post(self, action, site_id, visitor_id, ip):
        base, api_key = settings.questions_url, settings.DJANGO_SERVICE_API_KEY
        if not base or not api_key:
            return None
        return await self._http().post(
            base + action + "/",
            json={"site_id": str(site_id), "visitor_id": visitor_id, "ip_hash": self.ip_hash(ip)},
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )

    async def consume(self, site_id, visitor_id, ip):
        """Count one question; raise 429 `question_limit` when the visitor is over the limit."""
        try:
            response = await self._post("consume", site_id, visitor_id, ip)
            if response is None:
                return None
            data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            logger.warning("Question limit check failed for site %s (allowing): %s", site_id, type(error).__name__)
            return None

        if response.status_code != 200 or not isinstance(data, dict) or not isinstance(data.get("allowed"), bool):
            logger.warning("Question limit check for site %s returned HTTP %s (allowing)", site_id, response.status_code)
            return None

        if data["allowed"]:
            return data

        message = data.get("message") if isinstance(data.get("message"), str) and data.get("message") else DEFAULT_MESSAGE
        headers = {}
        retry_after = self._seconds_until(data.get("resets_at"))
        if retry_after:
            headers["Retry-After"] = str(retry_after)
        raise AppException(
            message,
            429,
            errors={"limit": data.get("limit"), "period": data.get("period"), "resets_at": data.get("resets_at")},
            code="question_limit",
            headers=headers,
        )

    async def refund(self, site_id, visitor_id, ip):
        """Give the question back after a failed reply (best effort)."""
        try:
            await self._post("refund", site_id, visitor_id, ip)
        except httpx.HTTPError as error:
            logger.warning("Question refund failed for site %s: %s", site_id, type(error).__name__)

    @staticmethod
    def _seconds_until(value):
        if not isinstance(value, str):
            return None
        try:
            resets_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        return max(int((resets_at - datetime.now(timezone.utc)).total_seconds()), 1)


question_limit_service = QuestionLimitService()
