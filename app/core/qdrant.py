from qdrant_client import QdrantClient
from app.config.settings import settings


class QdrantConnection:

    def __init__(self):
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT
        )

    def get_client(self):
        return self.client


qdrant_connection = QdrantConnection()


def get_qdrant_client():
    return qdrant_connection.get_client()