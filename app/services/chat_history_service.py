import json
from app.config.memory_store import memory_store

class ChatHistoryService:
    def __init__(self, store=None):
        self.store = store or memory_store

    def key(self, session_id):
        return f"chat:session:{session_id}"

    def add(self, session_id, role, content):
        key = self.key(session_id)

        self.store.rpush(
            key,
            json.dumps({
                "role": role,
                "content": content
            })
        )

        self.store.expire(key, 60)
        # self.store.expire(key, 60 * 60 * 24 * 30)


    def get(self, session_id):

        key = self.key(session_id)

        messages = self.store.lrange(key, -5, -1)

        return [json.loads(x) for x in messages]
