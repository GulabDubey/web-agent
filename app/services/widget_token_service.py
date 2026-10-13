import logging
import secrets
import time
from dataclasses import dataclass

from jose import ExpiredSignatureError, JWTError, jwt

from app.config.settings import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32


@dataclass(frozen=True)
class WidgetClaims:
    site_id: str
    customer_id: str
    site_key: str
    domain: str
    session_id: str
    expires_at: int


class WidgetTokenService:
    """Short-lived HS256 JWTs binding a chat session to one verified website."""

    def _secret(self):
        secret = settings.WIDGET_JWT_SECRET
        if (
            len(secret) < MIN_SECRET_LENGTH
            or secret == settings.DJANGO_SERVICE_API_KEY
            or secret in settings.internal_service_tokens
        ):
            logger.error(
                "WIDGET_JWT_SECRET is missing, shorter than %s characters, or reuses "
                "a service credential; widget tokens are disabled.",
                MIN_SECRET_LENGTH,
            )
            raise AppException("Service temporarily unavailable.", 503, code="service_unavailable")
        return secret

    @staticmethod
    def new_session_id():
        return secrets.token_urlsafe(18)

    def issue(self, site_id, customer_id, site_key, domain, session_id):
        now = int(time.time())
        expires_at = now + settings.WIDGET_TOKEN_TTL_SECONDS
        token = jwt.encode(
            {
                "iss": settings.WIDGET_TOKEN_ISSUER,
                "aud": settings.WIDGET_TOKEN_AUDIENCE,
                "sub": str(site_id),
                "cid": str(customer_id),
                "sk": site_key,
                "dom": domain,
                "sid": session_id,
                "iat": now,
                "exp": expires_at,
            },
            self._secret(),
            algorithm=ALGORITHM,
        )
        return token, expires_at

    def verify(self, token, allow_expired_within=0):
        """
        Check signature, algorithm, issuer, audience and expiry. With
        `allow_expired_within`, a token that expired at most that many
        seconds ago is accepted (used only by the refresh endpoint).
        """
        if not token:
            raise AppException("Missing widget token.", 401, code="token_missing")

        secret = self._secret()
        # python-jose enforces expiry whenever require_exp is set, so for a
        # refresh the presence/age of "exp" is checked manually below.
        options = {
            "require_exp": not allow_expired_within,
            "require_iat": True,
            "require_sub": True,
            "require_aud": True,
            "require_iss": True,
            "verify_exp": not allow_expired_within,
        }
        try:
            claims = jwt.decode(
                token,
                secret,
                algorithms=[ALGORITHM],
                audience=settings.WIDGET_TOKEN_AUDIENCE,
                issuer=settings.WIDGET_TOKEN_ISSUER,
                options=options,
            )
        except ExpiredSignatureError:
            raise AppException("Widget token expired.", 401, code="token_expired")
        except JWTError:
            raise AppException("Invalid widget token.", 401, code="token_invalid")

        expires_at = claims.get("exp")
        if not isinstance(expires_at, int):
            raise AppException("Invalid widget token.", 401, code="token_invalid")
        if allow_expired_within and expires_at + allow_expired_within < time.time():
            raise AppException("Widget token expired.", 401, code="token_expired")

        fields = [claims.get(name) for name in ("sub", "cid", "sk", "dom", "sid")]
        if not all(isinstance(value, str) and value for value in fields):
            raise AppException("Invalid widget token.", 401, code="token_invalid")

        return WidgetClaims(*fields, expires_at=expires_at)


widget_token_service = WidgetTokenService()
