import hashlib
from uuid import uuid4
from qdrant_client import QdrantClient
from qdrant_client.http.models import (PointStruct,Filter)
from app.core.qdrant import get_qdrant_client


class VectorRepository:

    def __init__(self, client: QdrantClient | None = None):
        self.client = client or get_qdrant_client()

    def generate_id(self, text: str) -> str:
        return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()

    def upsert(
        self,
        collection: str,
        vectors: list[list[float]],
        payloads: list[dict]
    ):

        points = []

        for vector, payload in zip(vectors, payloads):
            points.append(
                PointStruct(
                    id=str(uuid4()),
                    # id=self.generate_id(payload["content"]),
                    vector=vector,
                    payload=payload
                )
            )

        self.client.upsert(
            collection_name=collection,
            points=points
        )

    def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 5,
        filters: Filter | None = None
    ):

        result = self.client.query_points(
            collection_name=collection,
            query=query_vector,
            query_filter=filters,
            limit=limit
        )

        return result

    def delete(
        self,
        collection: str,
        point_ids: list[str]
    ):

        self.client.delete(
            collection_name=collection,
            points_selector=point_ids
        )

    def count(self, collection: str):

        return self.client.count(
            collection_name=collection
        )

    def collection_exists(self, collection: str):

        return self.client.collection_exists(collection)

    def create_collection(
        self,
        collection: str,
        vector_size: int
    ):

        from qdrant_client.http.models import VectorParams, Distance

        self.client.create_collection(
            collection_name=collection,
            vectors_config=VectorParams(
                size=vector_size,
                distance=Distance.COSINE
            )
        )