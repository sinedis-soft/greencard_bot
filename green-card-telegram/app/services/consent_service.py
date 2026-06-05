from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable


from app.db.models import Consent
from app.db.session import SessionLocal

REQUIRED_CONSENTS = ("terms_of_service", "privacy_policy", "personal_data_processing")
CONSENTS_PATH = Path(__file__).resolve().parents[1] / "consents" / "consents.yaml"
DEFAULT_CONSENTS = {
    "terms_of_service": {
        "version": "2026-06-01",
        "ru": "Я принимаю условия сервиса OC graniczne (border insurance) Agency и подтверждаю корректность данных заявки.",
        "en": "I accept the OC graniczne (border insurance) Agency terms of service and confirm that the application data is correct.",
    },
    "privacy_policy": {
        "version": "2026-06-01",
        "ru": "Я подтверждаю, что ознакомлен с политикой конфиденциальности OC graniczne (border insurance) Agency.",
        "en": "I confirm that I have read the OC graniczne (border insurance) Agency privacy policy.",
    },
    "personal_data_processing": {
        "version": "2026-06-01",
        "ru": "Я даю согласие на обработку персональных данных для оформления страхового полиса.",
        "en": "I consent to personal data processing for issuing the insurance policy.",
    },
}


class ConsentMissingError(ValueError):
    def __init__(self, missing: list[str]) -> None:
        self.missing = missing
        super().__init__("missing_required_consents:" + ",".join(missing))


def consent_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ConsentService:
    def __init__(self, path: Path = CONSENTS_PATH) -> None:
        self.path = path
        self._cache: dict | None = None

    def load_definitions(self) -> dict:
        if self._cache is None:
            self._cache = {"consents": DEFAULT_CONSENTS}
            if self.path.exists():
                try:
                    import yaml  # type: ignore

                    loaded = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
                    if isinstance(loaded.get("consents"), dict):
                        self._cache = loaded
                except Exception:
                    self._cache = {"consents": DEFAULT_CONSENTS}
        return self._cache.get("consents", {})

    def accepted_from_payload(self, payload) -> set[str]:
        explicit = set(getattr(payload, "accepted_consents", None) or [])
        if explicit:
            return explicit
        accepted: set[str] = set()
        if getattr(payload, "terms_accepted", False):
            accepted.add("terms_of_service")
        if getattr(payload, "privacy_accepted", False):
            accepted.add("privacy_policy")
            accepted.add("personal_data_processing")
        return accepted

    def validate_required(self, payload) -> set[str]:
        accepted = self.accepted_from_payload(payload)
        missing = [item for item in REQUIRED_CONSENTS if item not in accepted]
        if missing:
            raise ConsentMissingError(missing)
        return accepted

    def save_consents(
        self,
        application_id: int | None,
        telegram_user_id: int,
        language: str,
        accepted_consents: Iterable[str],
        source: str = "telegram_miniapp",
    ) -> None:
        definitions = self.load_definitions()
        lang = (language or "ru")[:10]
        with SessionLocal() as db:
            for consent_type in sorted(set(accepted_consents)):
                definition = definitions.get(consent_type)
                if not definition:
                    continue
                text = definition.get(lang) or definition.get("ru") or definition.get("en") or ""
                db.add(
                    Consent(
                        application_id=application_id,
                        telegram_user_id=telegram_user_id,
                        consent_type=consent_type,
                        consent_version=str(definition.get("version") or "unknown"),
                        language=lang,
                        consent_text_hash=consent_text_hash(text),
                        consent_text_snapshot=text,
                        source=source,
                    )
                )
            db.commit()
