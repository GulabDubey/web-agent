from app.repositories.vector_repository import VectorRepository
from app.services.embedding_service import EmbeddingService
from app.services.file_parser_service import FileParserService
from app.services.text_splitter_service import TextSplitterService

class VectorService:

    def __init__(
        self,
        repository: VectorRepository,
        embedding_service: EmbeddingService,
        fileParser: FileParserService,
        textSplitter: TextSplitterService,
    ):
        self.repository = repository
        self.embedding_service = embedding_service
        self.file_parser = fileParser
        self.text_splitter = textSplitter

    def create_collection(
        self,
        collection: str,
        vector_size: int = 1024
    ):

        if not self.repository.collection_exists(collection):

            self.repository.create_collection(
                collection,
                vector_size
            )

    def add_documents(
        self,
        collection: str,
        documents: list[dict],
    ):
        # Qdrant's upsert rejects an empty request outright (400 "Empty
        # update request"), so guard against that rather than letting it
        # bubble up as a confusing error from the repository layer.
        if not documents:
            return

        texts = [
            document["content"]
            for document in documents
        ]

        vectors = self.embedding_service.embed_documents(texts)

        payloads = []

        for document in documents:

            payloads.append({
                "content": document["content"],
                "source": document.get("source"),
                "file_name": document.get("file_name"),
                "page": document.get("page"),
                "metadata": document.get("metadata", {})
            })

        self.repository.upsert(
            collection=collection,
            vectors=vectors,
            payloads=payloads
        )

    def similarity_search(
        self,
        collection: str,
        query: str,
        limit: int = 3
    ):

        query_vector = self.embedding_service.embed_query(query)

        results = self.repository.search(
            collection=collection,
            query_vector=query_vector,
            limit=limit
        )

        response = []

        for item in results.points:

            response.append({
                "score": item.score,
                "content": item.payload.get("content"),
                "source": item.payload.get("source"),
                "metadata": item.payload.get("metadata")
            })

        return response

    def total_documents(
        self,
        collection: str
    ):

        return self.repository.count(collection)

    
    def extract_texts_from_files(self, files):
        pages = []
        for filepath in files:
            pagesData = self.file_parser.extract_text(filepath)
            pages.extend(pagesData)
        
        return pages
            
    def split_text_in_chunks(self, pages):
        chunks = self.text_splitter.split_text(pages)
        return chunks