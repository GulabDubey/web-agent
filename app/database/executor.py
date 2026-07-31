from sqlalchemy import text
from app.config.database import engine

class QueryExecutor:

    @staticmethod
    def execute(sql, params=None):

        with engine.connect() as conn:

            result = conn.execute(
                text(sql),
                params or {}
            )

            if result.returns_rows:
                return [dict(row._mapping) for row in result]

            conn.commit()

            return {
                "affected_rows": result.rowcount
            }