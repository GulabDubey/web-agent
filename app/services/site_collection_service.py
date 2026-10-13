import logging
import re

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from starlette.concurrency import run_in_threadpool

from app.config.settings import settings
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)

# Same rule as the Django field's validator; anything else is not trusted.
COLLECTION_RE = re.compile(r"^[A-Za-z0-9_-]{1,100}$")

QUERY = text("SELECT collection_name, is_active FROM websites_website WHERE id = :site_id")


class SiteCollectionService:
    """
    Reads a website's knowledge collection from the Django project's
    database (websites_website.collection_name). Read-only; the site id
    always comes from a verified widget token, never from the request.
    """

    def __init__(self, engine=None):
        self._engine = engine

    @property
    def engine(self):
        if self._engine is None:
            self._engine = create_engine(
                URL.create(
                    "mysql+pymysql",
                    username=settings.DJANGO_DB_USER or settings.DB_USER,
                    password=settings.DJANGO_DB_PASSWORD or settings.DB_PASSWORD,
                    host=settings.DJANGO_DB_HOST or settings.DB_HOST,
                    port=settings.DJANGO_DB_PORT,
                    database=settings.DJANGO_DB_NAME,
                ),
                pool_size=5,
                max_overflow=5,
                pool_pre_ping=True,
                pool_recycle=1800,
            )
        return self._engine

    def _fetch(self, site_id):
        with self.engine.connect() as connection:
            return connection.execute(QUERY, {"site_id": int(site_id)}).first()

    async def collection_for(self, site_id):
        try:
            row = await run_in_threadpool(self._fetch, site_id)
        except Exception:
            logger.exception("Could not read the knowledge collection for site %s", site_id)
            raise AppException(
                "Chatbot is temporarily unavailable. Please try again shortly.", 503, code="service_unavailable"
            )

        if row is None or not row.is_active:
            raise AppException("This website's chatbot is disabled.", 403, code="site_disabled")

        collection = (row.collection_name or "").strip()
        if not COLLECTION_RE.match(collection):
            logger.warning("Site %s has no valid collection_name configured", site_id)
            raise AppException(
                "This website's chatbot has no knowledge base yet.", 403, code="no_knowledge_base"
            )
        return collection


site_collection_service = SiteCollectionService()
