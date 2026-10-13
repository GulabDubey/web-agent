import hmac
import logging
import re
from dataclasses import dataclass

from fastapi import Request

from app.config.settings import settings
from app.core.domains import LOCAL_HOSTS, local_domain, normalize_domain, parse_origin
from app.core.exceptions import AppException
from app.services.rate_limit_service import rate_limit_service
from app.services.subscription_service import subscription_service
from app.services.website_crawler_service import WebsiteCrawlerService
from app.services.widget_token_service import WidgetClaims, widget_token_service

logger = logging.getLogger(__name__)

# Django generates "site_" + 32 url-safe characters; accept any url-safe
# key Django could store (max_length 64) and reject everything else early.
SITE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


@dataclass(frozen=True)
class WidgetContext:
    """Everything a protected chat endpoint may trust - all server-derived."""

    site_id: str
    customer_id: str
    site_key: str
    domain: str
    session_id: str
    collection: str

    @property
    def scoped_session_id(self):
        # Prefixing with the site keeps one tenant's sessions and history
        # unreachable from another tenant even if a session id leaked.
        return f"{self.site_id}:{self.session_id}"


def client_ip(request: Request):
    return request.client.host if request.client else "unknown"


def bearer_token(request: Request):
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


def request_domain(request: Request):
    """
    The registered domain this browser request comes from, from the Origin
    header. Origin can be forged by non-browser clients, so this only ever
    narrows access; the site key / token plus Django's check authorize.
    """
    parsed = parse_origin(request.headers.get("Origin"))
    if parsed is None:
        raise AppException("Missing or invalid Origin header.", 403, code="origin_invalid")

    scheme, host, port = parsed

    if host in LOCAL_HOSTS or host.endswith(".localhost"):
        if not settings.is_development:
            raise AppException("This origin is not allowed.", 403, code="origin_not_allowed")
        # WIDGET_DEV_DOMAIN, when set, makes local pages act as that
        # registered public domain. Otherwise the local origin itself
        # ("127.0.0.1:8012") is verified; Django accepts such domains only
        # when its DEBUG is on.
        dev_domain = normalize_domain(settings.WIDGET_DEV_DOMAIN)
        if dev_domain:
            return dev_domain
        if host in LOCAL_HOSTS:
            return local_domain(host, port)
        raise AppException("This origin is not allowed.", 403, code="origin_not_allowed")

    if scheme != "https" and not settings.is_development:
        raise AppException("The chatbot requires an HTTPS website.", 403, code="origin_not_allowed")

    domain = normalize_domain(host)
    if not domain:
        raise AppException("Missing or invalid Origin header.", 403, code="origin_invalid")

    allowed = {normalize_domain(item) for item in settings.widget_allowed_origins}
    if allowed and domain not in allowed:
        raise AppException("This origin is not allowed.", 403, code="origin_not_allowed")

    return domain


def collection_for(site_id, domain):
    """Knowledge collection for a verified site - never taken from the request."""
    collection = settings.WIDGET_SITE_COLLECTIONS.get(site_id)
    if collection:
        return collection
    return WebsiteCrawlerService.website_slug(f"https://{domain}")


def validate_site_key(request: Request, site_key):
    ip = client_ip(request)
    if rate_limit_service.is_blocked("badkey", ip, settings.RATE_LIMIT_INVALID_KEY_PER_IP, period=600):
        raise rate_limit_service.too_many(600)

    if not isinstance(site_key, str) or not SITE_KEY_RE.match(site_key):
        record_invalid_key(request)
        raise AppException("Missing or malformed site key.", 400, code="invalid_request")


def record_invalid_key(request: Request):
    rate_limit_service.hit("badkey", client_ip(request), 10**9, period=600)


async def authorize_site(request: Request, site_key, domain):
    """Django-backed authorization with invalid-key attempts counted per IP."""
    try:
        return await subscription_service.authorize(site_key, domain)
    except AppException as error:
        if error.status_code in (400, 403):
            record_invalid_key(request)
            logger.info(
                "Widget authorization denied (%s) for %s from %s", error.code, domain, client_ip(request)
            )
        raise


async def resolve_widget_context(request: Request, claims: WidgetClaims):
    domain = request_domain(request)
    if domain != claims.domain:
        logger.warning("Widget token for %s used from %s", claims.domain, domain)
        raise AppException("This origin is not allowed.", 403, code="origin_not_allowed")

    # Re-check the subscription (cached briefly) so cancellations apply
    # even to tokens issued earlier.
    auth = await authorize_site(request, claims.site_key, claims.domain)
    if auth.site_id != claims.site_id or auth.customer_id != claims.customer_id:
        logger.warning("Widget token site %s no longer matches site key", claims.site_id)
        raise AppException("Widget token is no longer valid.", 401, code="token_invalid")

    return WidgetContext(
        site_id=auth.site_id,
        customer_id=auth.customer_id,
        site_key=claims.site_key,
        domain=claims.domain,
        session_id=claims.session_id,
        collection=collection_for(auth.site_id, auth.domain),
    )


async def require_widget(request: Request) -> WidgetContext:
    """Dependency for every widget-facing endpoint that touches tenant data or the AI."""
    claims = widget_token_service.verify(bearer_token(request))
    return await resolve_widget_context(request, claims)


async def require_service_token(request: Request):
    """Dependency for server-to-server endpoints (crawl, ingest, users, cache invalidation)."""
    valid_tokens = settings.internal_service_tokens
    if not valid_tokens:
        logger.error("INTERNAL_SERVICE_TOKENS is not configured; rejecting %s", request.url.path)
        raise AppException("Service temporarily unavailable.", 503, code="service_unavailable")

    token = bearer_token(request).encode()
    matched = False
    for valid in valid_tokens:
        matched |= hmac.compare_digest(token, valid.encode())

    if not token or not matched:
        logger.warning("Rejected service call to %s from %s", request.url.path, client_ip(request))
        raise AppException("Unauthorized.", 401, code="unauthorized")
