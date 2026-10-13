from fastapi import APIRouter, Depends, Request
from app.config.settings import settings
from app.core.dependencies import get_vector_service
from app.core.widget_auth import WidgetContext, client_ip, require_service_token, require_widget
from app.core.exceptions import AppException
from app.schemas.chat_schema import ChatRequest, ContactUsRequest, ExtractWebsiteDataRequest
from app.services.chat_service import ChatService
from app.services.vector_service import VectorService
from app.services.redis_service import RedisService
from app.services.session_service import session_service
from app.services.validator_service import ValidatorService
from app.services.website_crawler_service import WebsiteCrawlerService
from app.core.response import ApiResponse
from app.services.question_service import QuestionService
from app.services.rate_limit_service import rate_limit_service
from app.config.question_config import QUESTIONS
from pathlib import Path

router = APIRouter()

chat_service = ChatService()
redis_service = RedisService()
question_service = QuestionService()

@router.post("/contact-us")
async def contact_us(request: ContactUsRequest, widget: WidgetContext = Depends(require_widget)):
    rate_limit_service.hit("contact:session", widget.scoped_session_id, 5)
    session = session_service.get(widget.scoped_session_id)

    if not ValidatorService.name(request.name):
        return ApiResponse.error(message="Please enter a valid name.")

    if not ValidatorService.email(request.email):
        return ApiResponse.error(message="Please enter a valid email address.")

    if not ValidatorService.mobile(request.contact):
        return ApiResponse.error(message="Please enter a valid 10-digit mobile number.")

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

    rate_limit_service.acquire_slot("chat", widget.site_id, settings.WIDGET_MAX_CONCURRENT_PER_SITE)
    try:
        redis_service.add(widget.scoped_session_id, "user", request.message)
        result = await chat_service.generate_reply(request.message, widget.collection)
    finally:
        rate_limit_service.release_slot("chat", widget.site_id)

    answer = result["reply"]["answer"]
    redis_service.add(widget.scoped_session_id, "assistant", answer)
    rate_limit_service.add_token_usage(widget.site_id, chat_service.token_usage(result, request.message))

    # Only the answer is returned; model metadata stays server-side.
    return ApiResponse.success(data={"message": answer}, message="Chat generated successfully!")

@router.post("/extract-website-data", dependencies=[Depends(require_service_token)])
async def extract_website_data(
    request: ExtractWebsiteDataRequest,
    vector_service: VectorService = Depends(get_vector_service),
):
    url = str(request.url)
    website = request.website or WebsiteCrawlerService.website_slug(url)

    try:
        files = await WebsiteCrawlerService.crawl_and_save(
            url,
            website=website,
            max_pages=request.max_pages,
        )
    except Exception as error:
        raise AppException(f"Failed to crawl website: {error}", 502)

    if not files:
        raise AppException("No content could be extracted from the given URL.", 422)

    pages = vector_service.extract_texts_from_files(files)
    chunks = vector_service.split_text_in_chunks(pages)

    if not chunks:
        raise AppException("No usable text content was found on the crawled pages.", 422)

    vector_service.create_collection(website)
    vector_service.add_documents(website, chunks)

    return ApiResponse.success(
        data={
            "website": website,
            "pages_crawled": len(files),
            "chunks_stored": len(chunks),
        },
        message="Website data extracted and stored successfully!",
    )

@router.post("/ingest-documents", dependencies=[Depends(require_service_token)])
async def ingest_documents(vector_service: VectorService = Depends(get_vector_service)):
    # files = [
    #     "storage/websites/companiesnext/001_companiesnext.txt",
    # ]
    website = "companiesnext"
    folder = Path(f"storage/websites/{website}")
    folder.mkdir(parents=True, exist_ok=True)
    files = [str(file) for file in folder.iterdir() if file.is_file()][75:]

    pages = vector_service.extract_texts_from_files(files)
    chunks = vector_service.split_text_in_chunks(pages)

    # return {"message": "File parsed successfully!", "data": {"pages":pages, "chunks":chunks}}

    vector_service.create_collection(website)
    vector_service.add_documents(
        website,
        chunks
    )

    return {"message": "PDF injested successfully!"}

    result = vector_service.similarity_search(
        "company_docs",
        "Do you know Gulab Dubey?"
    )

    return {"message": "Data fetched successfully!", "result": result}