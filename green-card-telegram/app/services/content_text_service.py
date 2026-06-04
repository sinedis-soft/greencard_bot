from __future__ import annotations

import os
import time
from datetime import datetime

from sqlalchemy import select

from app.db.models import ContentText
from app.db.session import SessionLocal


class ContentTextService:
    CACHE_TTL_SECONDS = 300
    _memory_cache: dict[str, tuple[str, float]] = {}

    def __init__(self) -> None:
        self.redis = None
        url = os.getenv("REDIS_URL")
        if url:
            try:
                from redis import Redis  # type: ignore

                self.redis = Redis.from_url(url, decode_responses=True)
            except Exception:
                self.redis = None

    def get(self, key: str, language: str = "ru", fallback_languages: tuple[str, ...] = ("ru", "en")) -> str | None:
        languages = (language, *[lang for lang in fallback_languages if lang != language])
        for lang in languages:
            cached = self._cache_get(key, lang)
            if cached is not None:
                return cached
            text = self._db_get(key, lang)
            if text is not None:
                self._cache_set(key, lang, text)
                return text
        return None

    def list_texts(self, category: str | None = None, language: str | None = None, active_only: bool = False) -> list[dict]:
        with SessionLocal() as db:
            stmt = select(ContentText).order_by(ContentText.category, ContentText.key, ContentText.language, ContentText.created_at.desc())
            if category:
                stmt = stmt.where(ContentText.category == category)
            if language:
                stmt = stmt.where(ContentText.language == language)
            if active_only:
                stmt = stmt.where(ContentText.is_active == True)
            return [self._to_dict(item) for item in db.scalars(stmt)]

    def create_text(self, data: dict) -> dict:
        with SessionLocal() as db:
            item = ContentText(
                key=str(data["key"]),
                language=str(data.get("language") or "ru"),
                category=str(data.get("category") or "notification"),
                text=str(data["text"]),
                version=data.get("version"),
                is_active=bool(data.get("is_active", True)),
            )
            db.add(item)
            db.commit()
            db.refresh(item)
            self.invalidate(item.key, item.language)
            return self._to_dict(item)

    def update_text(self, text_id: int, data: dict) -> dict | None:
        with SessionLocal() as db:
            item = db.get(ContentText, text_id)
            if not item:
                return None
            old_key, old_language = item.key, item.language
            for key in ("key", "language", "category", "text", "version"):
                if key in data:
                    setattr(item, key, str(data[key]) if data[key] is not None else None)
            if "is_active" in data:
                item.is_active = bool(data["is_active"])
            item.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(item)
            self.invalidate(old_key, old_language)
            self.invalidate(item.key, item.language)
            return self._to_dict(item)

    def set_active(self, text_id: int, is_active: bool) -> dict | None:
        return self.update_text(text_id, {"is_active": is_active})

    def invalidate(self, key: str, language: str) -> None:
        cache_key = self._cache_key(key, language)
        self._memory_cache.pop(cache_key, None)
        if self.redis is not None:
            try:
                self.redis.delete(cache_key)
            except Exception:
                self.redis = None

    def _db_get(self, key: str, language: str) -> str | None:
        with SessionLocal() as db:
            item = db.scalar(
                select(ContentText)
                .where(ContentText.key == key, ContentText.language == language, ContentText.is_active == True)
                .order_by(ContentText.created_at.desc())
            )
            return item.text if item else None

    def _cache_get(self, key: str, language: str) -> str | None:
        cache_key = self._cache_key(key, language)
        if self.redis is not None:
            try:
                return self.redis.get(cache_key)
            except Exception:
                self.redis = None
        cached = self._memory_cache.get(cache_key)
        if not cached:
            return None
        value, expires_at = cached
        if expires_at <= time.time():
            self._memory_cache.pop(cache_key, None)
            return None
        return value

    def _cache_set(self, key: str, language: str, text: str) -> None:
        cache_key = self._cache_key(key, language)
        if self.redis is not None:
            try:
                self.redis.setex(cache_key, self.CACHE_TTL_SECONDS, text)
                return
            except Exception:
                self.redis = None
        self._memory_cache[cache_key] = (text, time.time() + self.CACHE_TTL_SECONDS)

    @staticmethod
    def _cache_key(key: str, language: str) -> str:
        return f"content:{language}:{key}"

    @staticmethod
    def _to_dict(item: ContentText) -> dict:
        return {
            "id": item.id,
            "key": item.key,
            "language": item.language,
            "category": item.category,
            "text": item.text,
            "version": item.version,
            "is_active": item.is_active,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }
