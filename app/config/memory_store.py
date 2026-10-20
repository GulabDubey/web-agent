import fnmatch
import threading
import time


class MemoryStore:
    """
    Process-local key/value store with expiry, covering the Redis commands
    the app used (rate limits, authorization cache, chat history).

    State is per instance: limits and caches are not shared across workers
    or serverless instances, and reset on restart.
    """

    def __init__(self):
        self.data = {}
        self.expiry = {}
        self._lock = threading.RLock()

    def _alive(self, key):
        if key in self.expiry and self.expiry[key] <= time.time():
            self.data.pop(key, None)
            self.expiry.pop(key, None)
        return key in self.data

    def get(self, key):
        with self._lock:
            return self.data[key] if self._alive(key) else None

    def set(self, key, value, ex=None):
        with self._lock:
            self.data[key] = str(value)
            if ex:
                self.expiry[key] = time.time() + ex
            else:
                self.expiry.pop(key, None)
            return True

    def incrby(self, key, amount):
        with self._lock:
            value = int(self.get(key) or 0) + amount
            self.data[key] = str(value)
            return value

    def incr(self, key):
        return self.incrby(key, 1)

    def decr(self, key):
        return self.incrby(key, -1)

    def expire(self, key, seconds):
        with self._lock:
            if self._alive(key):
                self.expiry[key] = time.time() + seconds

    def delete(self, *keys):
        with self._lock:
            for key in keys:
                self.data.pop(key, None)
                self.expiry.pop(key, None)

    def rpush(self, key, value):
        with self._lock:
            if not self._alive(key):
                self.data[key] = []
            self.data[key].append(value)

    def lrange(self, key, start, end):
        with self._lock:
            values = self.data[key] if self._alive(key) else []
            return values[start:] if end == -1 else values[start:end + 1]

    def keys(self, pattern="*"):
        with self._lock:
            return [key for key in list(self.data) if self._alive(key) and fnmatch.fnmatch(key, pattern)]


memory_store = MemoryStore()
