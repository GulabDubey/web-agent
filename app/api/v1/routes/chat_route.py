from fastapi import APIRouter, Depends
from app.core.dependencies import get_vector_service
from app.schemas.chat_schema import ChatRequest, ContactUsRequest
from app.services.chat_service import ChatService
from app.services.vector_service import VectorService
from app.services.redis_service import RedisService
from app.services.session_service import session_service
from app.services.validator_service import ValidatorService
from app.core.response import ApiResponse
from app.services.question_service import QuestionService
from app.config.question_config import QUESTIONS
from pathlib import Path

router = APIRouter()

chat_service = ChatService()
redis_service = RedisService()
question_service = QuestionService()

@router.post("/contact-us")
async def contact_us(request: ContactUsRequest):
    session = session_service.get(request.session_id)

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
async def chat(request: ChatRequest):
    session = session_service.get(request.session_id)
    redis_service.add(request.session_id, "user", request.message)
    result = await chat_service.generate_reply(request.message)
    redis_service.add(request.session_id, "assistant", result["reply"]["answer"])
    
    return ApiResponse.success(data={
        "message": result["reply"]["answer"],
        "reply": result
    },
        message="Chat generated successfully!"
    )

@router.post("/extract-website-data")
async def extract_website_data():
    # Folder and file path
    folder = Path("storage/websites")
    file_path = folder / "companiesnext.txt"

    # Create folder if it doesn't exist
    folder.mkdir(parents=True, exist_ok=True)

    file_path.write_text("Hello, this is the initial content2.\n")
    print("File created with content")

    return ApiResponse.success(data={"message": "Website-data extracted successfully!"}, message="Website-data extracted successfully!")

@router.post("/ingest-documents")
async def ingest_documents(vector_service: VectorService = Depends(get_vector_service)):
    # files = [
    #     "storage/websites/companiesnext/001_companiesnext.txt",
    # ]
    website = "companiesnext"
    folder = Path(f"storage/websites/{website}")
    folder.mkdir(parents=True, exist_ok=True)
    files = [str(file) for file in folder.iterdir() if file.is_file()][75:]
    print(files)

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