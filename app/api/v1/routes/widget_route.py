from fastapi import APIRouter, Depends, Request

from app.config.settings import settings
from app.core.response import ApiResponse
from app.core.widget_auth import (
    authorize_site,
    bearer_token,
    client_ip,
    request_domain,
    require_service_token,
    resolve_widget_context,
    validate_site_key,
)
from app.schemas.widget_schema import InvalidateSiteRequest, WidgetSessionRequest
from app.services.rate_limit_service import rate_limit_service
from app.services.llm_config_service import llm_config_service
from app.services.subscription_service import subscription_service
from app.services.widget_token_service import widget_token_service

router = APIRouter(tags=["Widget"])


def token_response(context_or_auth, site_key, domain, session_id, message, visitor_id):
    token, expires_at = widget_token_service.issue(
        site_id=context_or_auth.site_id,
        customer_id=context_or_auth.customer_id,
        site_key=site_key,
        domain=domain,
        session_id=session_id,
        visitor_id=visitor_id,
    )
    return ApiResponse.success(
        data={
            "visitor_id": visitor_id,
            "token": token,
            "token_type": "Bearer",
            "expires_in": settings.WIDGET_TOKEN_TTL_SECONDS,
            "expires_at": expires_at,
        },
        message=message,
    )


@router.post("/widget/session")
async def create_session(payload: WidgetSessionRequest, request: Request):
    """Exchange a public site key for a short-lived widget token."""
    validate_site_key(request, payload.site_key)
    domain = request_domain(request)

    rate_limit_service.hit("session:ip", client_ip(request), settings.RATE_LIMIT_SESSIONS_PER_IP)
    rate_limit_service.hit("session:key", payload.site_key, settings.RATE_LIMIT_SESSIONS_PER_SITE)

    auth = await authorize_site(request, payload.site_key, domain)

    visitor_id = (
        payload.visitor_id if widget_token_service.valid_visitor_id(payload.visitor_id)
        else widget_token_service.new_visitor_id()
    )
    return token_response(
        auth, payload.site_key, domain, widget_token_service.new_session_id(), "Widget session created.", visitor_id
    )


@router.post("/widget/token/refresh")
async def refresh_token(request: Request):
    """New token for the same chat session; subscription and origin are re-checked."""
    claims = widget_token_service.verify(
        bearer_token(request),
        allow_expired_within=settings.WIDGET_TOKEN_REFRESH_GRACE_SECONDS,
    )
    rate_limit_service.hit("session:ip", client_ip(request), settings.RATE_LIMIT_SESSIONS_PER_IP)

    context = await resolve_widget_context(request, claims)

    return token_response(
        context, context.site_key, context.domain, context.session_id, "Widget token refreshed.", context.visitor_id
    )


@router.post("/internal/widget/invalidate", dependencies=[Depends(require_service_token)])
async def invalidate_site(payload: InvalidateSiteRequest):
    """Django calls this after a cancellation/suspension so it applies immediately."""
    subscription_service.invalidate(payload.site_key)
    # Provider/model/key changes should also apply right away.
    llm_config_service.clear()
    return ApiResponse.success(message="Cached authorization cleared.")
