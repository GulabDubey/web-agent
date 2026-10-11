from sentence_transformers import SentenceTransformer
from app.config.settings import settings

class EmbeddingService:
    _model = None

    def __init__(self):
        if self.__class__._model is None:
            self.__class__._model = SentenceTransformer(
                "BAAI/bge-large-en-v1.5",
                # An empty string (vs. unset) would make huggingface_hub send
                # an "Authorization: Bearer " header, which httpx rejects as
                # malformed. `None` skips auth entirely - fine for this
                # public model; set HF_TOKEN for gated/private ones.
                token=settings.HF_TOKEN or None
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