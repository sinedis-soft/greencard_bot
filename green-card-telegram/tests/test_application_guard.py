from app.services.pii_hashing import normalize_email, normalize_phone, normalize_plate, normalize_vin, pii_hash
from app.services.rate_limit_service import RateLimitService


def test_pii_normalization_before_hmac_hashing():
    assert normalize_phone("+374 (55) 12-34-56") == "37455123456"
    assert normalize_email("  USER@Example.COM ") == "user@example.com"
    assert normalize_plate(" am-123 ab ") == "AM123AB"
    assert normalize_vin(" wvw zzz 1jz ") == "WVWZZZ1JZ"


def test_pii_hash_is_hmac_and_secret_dependent():
    value = normalize_plate("AM 123 AB")
    first = pii_hash(value, "secret-one")
    assert first == pii_hash(value, "secret-one")
    assert first != pii_hash(value, "secret-two")
    assert first != value


def test_rate_limit_service_in_memory_fallback_enforces_limits():
    service = RateLimitService(redis_url=None)
    key = "test:rate:guard"
    assert service.check_and_increment(key, limit=2, ttl_seconds=60).allowed is True
    assert service.check_and_increment(key, limit=2, ttl_seconds=60).allowed is True
    exceeded = service.check_and_increment(key, limit=2, ttl_seconds=60)
    assert exceeded.allowed is False
    assert exceeded.count == 3
