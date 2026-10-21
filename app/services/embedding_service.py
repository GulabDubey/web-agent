import httpx

from app.config.settings import settings

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
# Voyage accepts up to 1000 inputs per request; smaller batches keep each
# request well under its per-request token limit.
BATCH_SIZE = 128


class EmbeddingService:
    """
    Embeds text through the Voyage AI API (VOYAGE_MODEL, EMBEDDING_DIMENSION).

    Qdrant collections must be built with the same model and dimension, or
    similarity scores are meaningless. Voyage returns unit-length vectors,
    so cosine distance works as-is.
    """

    _client = None

    def __init__(self):
        if self.__class__._client is None:
            self.__class__._client = httpx.Client(
                timeout=httpx.Timeout(30.0, connect=5.0),
                headers={"Authorization": f"Bearer {settings.VOYAGE_API_KEY}"},
            )

        self.client = self.__class__._client

    def _embed(self, texts: list[str], input_type: str) -> list[list[float]]:
        response = self.client.post(
            VOYAGE_URL,
            json={
                "input": texts,
                "model": settings.VOYAGE_MODEL,
                "input_type": input_type,
                "output_dimension": settings.EMBEDDING_DIMENSION,
            },
        )
        response.raise_for_status()

        data = sorted(response.json()["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in data]

    def embed_documents(
        self,
        texts: list[str]
    ) -> list[list[float]]:

        vectors = []
        for start in range(0, len(texts), BATCH_SIZE):
            vectors.extend(self._embed(texts[start:start + BATCH_SIZE], "document"))
        return vectors

    def embed_query(
        self,
        text: str
    ) -> list[float]:

        return self._embed([text], "query")[0]
