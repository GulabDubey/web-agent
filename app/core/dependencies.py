from app.services.auth_service import AuthService
from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService
from app.repositories.vector_repository import VectorRepository
from app.services.vector_service import VectorService
from app.services.embedding_service import EmbeddingService
from app.services.file_parser_service import FileParserService
from app.services.text_splitter_service import TextSplitterService
from fastapi import Depends
from app.config.database import get_db

def get_auth_service(db = Depends(get_db)):
    repository = UserService()
    return AuthService(repository)

def get_user_service(db = Depends(get_db)):
    repository = UserRepository(db)

    return UserService(repository)

def get_vector_service():

    repository = VectorRepository()
    embedding = EmbeddingService()
    fileParser = FileParserService()
    textSplitter = TextSplitterService()

    return VectorService(
        repository,
        embedding,
        fileParser,
        textSplitter,
    )