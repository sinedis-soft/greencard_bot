from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import ClassVar


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int


class RateLimitService:
    APPLICATIONS_PER_HOUR = 3
    OPERATOR_MESSAGES_PER_HOUR = 20
    OPERATOR_MESSAGES_PER_DAY = 40

    _memory: ClassVar[dict[str, tuple[int, float]]] = {}

    def __init__(self, redis_url: str | None = None) -> None:
        self.redis = None
        url = redis_url or os.getenv("REDIS_URL")
        if url:
            try:
                from redis import Redis  # type: ignore

                self.redis = Redis.from_url(url, decode_responses=True)
            except Exception:
                self.redis = None

    def check_and_increment(self, key: str, limit: int, ttl_seconds: int) -> RateLimitResult:
        if self.redis is not None:
            try:
                count = int(self.redis.incr(key))
                if count == 1:
                    self.redis.expire(key, ttl_seconds)
                ttl = int(self.redis.ttl(key) or ttl_seconds)
                return RateLimitResult(count <= limit, count, limit, max(ttl, 0))
            except Exception:
                self.redis = None
        return self._memory_check(key, limit, ttl_seconds)

    def _memory_check(self, key: str, limit: int, ttl_seconds: int) -> RateLimitResult:
        now = time.time()
        count, expires_at = self._memory.get(key, (0, now + ttl_seconds))
        if expires_at <= now:
            count, expires_at = 0, now + ttl_seconds
        count += 1
        self._memory[key] = (count, expires_at)
        return RateLimitResult(count <= limit, count, limit, int(max(expires_at - now, 0)))

    def check_application_create(self, telegram_user_id: int) -> RateLimitResult:
        return self.check_and_increment(
            f"rate:applications:hour:{telegram_user_id}",
            self.APPLICATIONS_PER_HOUR,
            3600,
        )

    def check_operator_message(self, telegram_user_id: int) -> tuple[RateLimitResult, RateLimitResult]:
        hour = self.check_and_increment(
            f"rate:operator_messages:hour:{telegram_user_id}",
            self.OPERATOR_MESSAGES_PER_HOUR,
            3600,
        )
        day = self.check_and_increment(
            f"rate:operator_messages:day:{telegram_user_id}",
            self.OPERATOR_MESSAGES_PER_DAY,
            86400,
        )
        return hour, day
