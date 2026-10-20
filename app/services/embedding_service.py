import math

from huggingface_hub import InferenceClient
from app.config.settings import settings

# Must match the model used to build the Qdrant collections locally
# (1024-dim, normalized), or similarity scores are meaningless.
EMBEDDING_MODEL = "BAAI/bge-large-en-v1.5"


class EmbeddingService:
    """
    Embeds text through the Hugging Face Inference API, so the deployed
    app does not ship torch/sentence-transformers.
    """

    _client = None

    def __init__(self):
        if self.__class__._client is None:
            self.__class__._client = InferenceClient(
                model=EMBEDDING_MODEL,
                # An empty string (vs. unset) would send a malformed
                # "Authorization: Bearer " header; `None` skips auth.
                token=settings.HF_TOKEN or None,
                timeout=30,
            )

        self.client = self.__class__._client

    @staticmethod
    def _normalize(vector) -> list[float]:
        values = [float(x) for x in vector]
        norm = math.sqrt(sum(x * x for x in values)) or 1.0
        return [x / norm for x in values]

    def _embed(self, text: str) -> list[float]:
        vector = self.client.feature_extraction(text)
        # Some providers return token-level output [[...]]; take the CLS
        # token, matching bge's sentence-transformers pooling.
        if hasattr(vector, "tolist"):
            vector = vector.tolist()
        while vector and isinstance(vector[0], list):
            vector = vector[0]
        return self._normalize(vector)

    def embed_documents(
        self,
        texts: list[str]
    ) -> list[list[float]]:

        return [self._embed(text) for text in texts]

    def embed_query(
        self,
        text: str
    ) -> list[float]:

        return self._embed(text)
