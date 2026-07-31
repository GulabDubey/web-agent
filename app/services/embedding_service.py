from sentence_transformers import SentenceTransformer
from app.config.settings import settings

class EmbeddingService:
    _model = None

    def __init__(self):
        if self.__class__._model is None:
            print("Loading embedding model...")
            self.__class__._model = SentenceTransformer(
                "BAAI/bge-large-en-v1.5",
                token=settings.HF_TOKEN
            )

        self.model = self.__class__._model

    def embed_documents(
        self,
        texts: list[str]
    ) -> list[list[float]]:

        return self.model.encode(
            texts,
            normalize_embeddings=True
        ).tolist()

    def embed_query(
        self,
        text: str
    ) -> list[float]:

        return self.model.encode(
            text,
            normalize_embeddings=True
        ).tolist()