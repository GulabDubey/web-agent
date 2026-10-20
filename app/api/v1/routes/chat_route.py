from fastapi import APIRouter, Depends, Request
from app.config.settings import settings
from app.core.widget_auth import WidgetContext, client_ip, require_widget
from app.schemas.chat_schema import ChatRequest, ContactUsRequest
from app.services.chat_service import ChatService
from app.services.chat_history_service import ChatHistoryService
from app.services.session_service import session_service
from app.services.validator_service import ValidatorService
from app.core.response import ApiResponse
from app.services.question_service import QuestionService
from app.services.rate_limit_service import rate_limit_service
from app.services.site_collection_service import site_collection_service

router = APIRouter()

chat_service = ChatService()
chat_history_service = ChatHistoryService()
question_service = QuestionService()

@router.post("/contact-us")
async def contact_us(request: ContactUsRequest, widget: WidgetContext = Depends(require_widget)):
    rate_limit_service.hit("contact:session", widget.scoped_session_id, 5)
    session = session_service.get(widget.scoped_session_id)

    if not ValidatorService.name(request.name):
        return ApiResponse.error(message="Please enter a valid name.")

    if not ValidatorService.email(request.email):
        return ApiResponse.error(message="Please enter a valid email address.")

    if not ValidatorService.mobile(request.contact, request.country_code):
        return ApiResponse.error(message="Please enter a valid mobile number.")

    session.answers["name"] = request.name
    session.answers["email"] = request.email
    session.answers["mobile"] = request.contact
    session.answers["country_code"] = request.country_code

    # name, email and mobile are answered by the form; resume the
    # conversational flow from the next unanswered question.
    session.current_question = 3

    question = question_service.next_question(session)

    return ApiResponse.success(
        data={
            "type": "question",
            "key": question.key if question else None,
            "message": question.text if question else "How can we help you today?",
        },
        message="Contact details saved successfully!"
    )

@router.post("/chat")
async def chat(request: ChatRequest, http_request: Request, widget: WidgetContext = Depends(require_widget)):
    # All limits are checked before the (paid) AI call starts.
    rate_limit_service.hit("chat:session", widget.scoped_session_id, settings.RATE_LIMIT_CHAT_PER_SESSION)
    rate_limit_service.hit("chat:ip", client_ip(http_request), settings.RATE_LIMIT_CHAT_PER_IP)
    rate_limit_service.hit("chat:site", widget.site_id, settings.RATE_LIMIT_CHAT_PER_SITE)
    rate_limit_service.check_token_budget(widget.site_id, settings.WIDGET_DAILY_TOKEN_LIMIT_PER_SITE)

    # Knowledge base of the verified site, read from Django's websites table.
    collection = await site_collection_service.collection_for(widget.site_id)

    rate_limit_service.acquire_slot("chat", widget.site_id, settings.WIDGET_MAX_CONCURRENT_PER_SITE)
    try:
        chat_history_service.add(widget.scoped_session_id, "user", request.message)
        result = await chat_service.generate_reply(request.message, collection)
    finally:
        rate_limit_service.release_slot("chat", widget.site_id)

    answer = result["reply"]["answer"] or (
        "Sorry, I couldn't put together an answer to that. Could you rephrase your question?"
    )
    chat_history_service.add(widget.scoped_session_id, "assistant", answer)
    rate_limit_service.add_token_usage(widget.site_id, chat_service.token_usage(result, request.message))

    # Only the answer is returned; model metadata stays server-side.
    return ApiResponse.success(data={"message": answer}, message="Chat generated successfully!")
