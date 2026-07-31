from math import ceil

class BaseRepository:
    def __init__(self, db):
        self.db = db

    def save(self, obj):
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def delete(self, obj):
        self.db.delete(obj)
        self.db.commit()
        
    def paginate(self, query, page=1, per_page=10):
        total = query.count()

        items = (
            query.offset((page - 1) * per_page)
                 .limit(per_page)
                 .all()
        )

        return {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
            "pages": ceil(total / per_page) if total else 0,
        }