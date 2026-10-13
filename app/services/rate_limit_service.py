import logging
import time

from app.config.redis import RedisClient
from app.core.exceptions import AppException

logger = logging.getLogger(__name__)


class RateLimitService:
    """
    Fixed-window counters in the shared Redis, so limits hold across
    workers and instances. A Redis outage fails closed (503).
    """

    def __init__(self, redis=None):
        self._redis = redis

    @property
    def redis(self):
        return self._redis or RedisClient().client

    def _call(self, fn, *args):
        try:
            return fn(*args)
        except AppException:
            raise
        except Exception:
            logger.exception("Rate limiter unavailable")
            raise AppException("Service temporarily unavailable.", 503, code="service_unavailable")

    def hit(self, name, ident, limit, period=60):
        """Count one request; raise 429 once `limit` is exceeded in the window."""
        if limit <= 0:
            return

        window = int(time.time() // period)
        key = f"rl:{name}:{ident}:{window}"

        def run():
            count = self.redis.incr(key)
            if count == 1:
                self.redis.expire(key, period)
            return count

        if self._call(run) > limit:
            raise self.too_many(period - int(time.time()) % period)

    def is_blocked(self, name, ident, limit, period=60):
        """True if `limit` is already reached, without counting this request."""
        window = int(time.time() // period)
        count = self._call(lambda: self.redis.get(f"rl:{name}:{ident}:{window}"))
        return limit > 0 and int(count or 0) >= limit

    @staticmethod
    def too_many(retry_after):
        return AppException(
            "Too many requests. Please try again later.",
            429,
            code="rate_limited",
            headers={"Retry-After": str(max(int(retry_after), 1))},
        )

    def acquire_slot(self, name, ident, limit, ttl=120):
        """Reserve a concurrency slot; pair with release_slot in a finally."""
        if limit <= 0:
            return False

        key = f"conc:{name}:{ident}"

        def run():
            count = self.redis.incr(key)
            # Safety net so a crashed worker cannot leak slots forever.
            self.redis.expire(key, ttl)
            if count > limit:
                self.redis.decr(key)
                return False
            return True

        if not self._call(run):
            raise self.too_many(5)
        return True

    def release_slot(self, name, ident):
        try:
            self.redis.decr(f"conc:{name}:{ident}")
        except Exception:
            logger.exception("Failed to release concurrency slot")

    def usage_key(self, site_id):
        return f"usage:tokens:{site_id}:{time.strftime('%Y%m%d', time.gmtime())}"

    def check_token_budget(self, site_id, limit):
        if limit <= 0:
            return
        used = self._call(lambda: self.redis.get(self.usage_key(site_id)))
        if int(used or 0) >= limit:
            raise AppException(
                "Daily chat limit reached for this website. Please try again tomorrow.",
                429,
                code="usage_limit",
            )

    def add_token_usage(self, site_id, tokens):
        if tokens <= 0:
            return
        key = self.usage_key(site_id)
        try:
            self.redis.incrby(key, int(tokens))
            self.redis.expire(key, 2 * 24 * 3600)
        except Exception:
            logger.exception("Failed to record token usage for site %s", site_id)


rate_limit_service = RateLimitService()
