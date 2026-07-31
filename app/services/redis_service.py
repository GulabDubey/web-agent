import json
from app.config.redis import RedisClient

class RedisService:
    def __init__(self):
        self.redis = RedisClient().client

    def key(self, session_id):
        return f"chat:session:{session_id}"

    def add(self, session_id, role, content):
        key = self.key(session_id)

        self.redis.rpush(
            key,
            json.dumps({
                "role": role,
                "content": content
            })
        )

        self.redis.expire(key, 60)
        # self.redis.expire(key, 60 * 60 * 24 * 30)


    def get(self, session_id):

        key = self.key(session_id)

        messages = self.redis.lrange(key, -5, -1)

        return [json.loads(x) for x in messages]