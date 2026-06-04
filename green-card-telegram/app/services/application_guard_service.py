from __future__ import annotations

from dataclasses import dataclass, field

from app.services.blocked_user_service import BlockedUserService
from app.services.consent_service import ConsentMissingError, ConsentService
from app.services.duplicate_check_service import DuplicateCheckResult, DuplicateCheckService
from app.services.file_storage_service import MAX_FILES
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload
from app.services.rate_limit_service import RateLimitService


@dataclass(frozen=True)
class ApplicationGuardResult:
    allowed: bool
    code: str = "ok"
    message: str = "ok"
    severity: str = "none"
    actions: dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "actions": self.actions,
        }


class ApplicationGuardService:
    def __init__(
        self,
        duplicate_service: DuplicateCheckService | None = None,
        consent_service: ConsentService | None = None,
        rate_limit_service: RateLimitService | None = None,
        blocked_user_service: BlockedUserService | None = None,
        ticket_service: OperatorTicketService | None = None,
    ) -> None:
        self.duplicates = duplicate_service or DuplicateCheckService()
        self.consents = consent_service or ConsentService()
        self.rate_limits = rate_limit_service or RateLimitService()
        self.blocked_users = blocked_user_service or BlockedUserService()
        self.tickets = ticket_service or OperatorTicketService()

    def check_before_create(self, payload, telegram_user_id: int, file_count: int, allow_duplicate_override: bool = False) -> ApplicationGuardResult:
        block = self.blocked_users.get_active_block(telegram_user_id)
        if block:
            return ApplicationGuardResult(False, "blocked_user", "Ваш доступ временно ограничен. Если это ошибка, обратитесь к оператору.", "hard", {"contact_operator": True})

        rate = self.rate_limits.check_application_create(telegram_user_id)
        if not rate.allowed:
            return ApplicationGuardResult(False, "rate_limit_applications", "Вы создали слишком много заявок за короткое время. Пожалуйста, попробуйте позже или напишите оператору.", "hard", {"contact_operator": True})

        if file_count > MAX_FILES:
            return ApplicationGuardResult(False, "too_many_files", "Можно загрузить не более 9 файлов на заявку.", "hard", {})

        try:
            self.consents.validate_required(payload)
        except ConsentMissingError as exc:
            return ApplicationGuardResult(False, "missing_required_consents", "Для подачи заявки необходимо принять обязательные согласия на условия сервиса, конфиденциальность и обработку данных.", "hard", {"missing": exc.missing})

        duplicate = self.duplicates.check_local(telegram_user_id, self.duplicates.build_hashes(payload))
        if duplicate.found:
            return self._duplicate_result(payload, telegram_user_id, duplicate, allow_duplicate_override)

        return ApplicationGuardResult(True)

    def _duplicate_result(self, payload, telegram_user_id: int, duplicate: DuplicateCheckResult, allow_duplicate_override: bool) -> ApplicationGuardResult:
        if duplicate.reason == "duplicate_vin":
            self._create_duplicate_vin_ticket(payload, telegram_user_id, duplicate)
            return ApplicationGuardResult(False, "duplicate_vin", "По этому VIN уже есть активная заявка. Мы передали запрос оператору для проверки.", "hard", {"contact_operator": True})
        if duplicate.reason == "duplicate_plate" and not allow_duplicate_override:
            return ApplicationGuardResult(False, "duplicate_plate", "По этому госномеру уже есть активная заявка. Откройте её в разделе «Мои заявки» или свяжитесь с оператором.", "medium", {"my_applications": True, "contact_operator": True})
        if duplicate.reason == "active_application" and not allow_duplicate_override:
            return ApplicationGuardResult(False, "active_application", "У вас уже есть активная заявка за последние 24 часа. Вы можете открыть её в разделе «Мои заявки» или связаться с оператором.", "soft", {"my_applications": True, "contact_operator": True, "allow_override": True})
        return ApplicationGuardResult(True)

    def _create_duplicate_vin_ticket(self, payload, telegram_user_id: int, duplicate: DuplicateCheckResult) -> None:
        first_vehicle = (getattr(payload, "vehicles", None) or [None])[0]
        request_id = f"DUP-{telegram_user_id}-{getattr(duplicate.duplicate, 'id', 'vin')}"
        self.tickets.create_or_get_ticket(
            TicketPayload(
                request_id=request_id[:64],
                telegram_user_id=telegram_user_id,
                telegram_chat_id=None,
                bitrix_deal_id=getattr(duplicate.duplicate, "bitrix_deal_id", None),
                reason="duplicate_vin_detected",
                priority="high",
                client_name="",
                client_phone="",
                preferred_language=getattr(payload, "preferred_language", "ru"),
                vehicle_type=getattr(first_vehicle, "vehicle_type", ""),
                license_plate="",
                vin="",
                insurance_period_days=getattr(first_vehicle, "insurance_period_days", 0),
                insurance_start_date=str(getattr(first_vehicle, "insurance_start_date", "")),
                comment="Обнаружен дубль заявки по HMAC-хэшу VIN. Полные данные смотрите в Bitrix.",
                last_message_preview="Обнаружен дубль заявки по VIN.",
            )
        )

    def record_application(self, application_id: int | None, telegram_user_id: int, payload, status: str = "submitted") -> None:
        self.duplicates.index_application(application_id, telegram_user_id, payload, status=status)

    def update_application_status(self, application_id: int | None, status: str, bitrix_deal_id: int | None = None) -> None:
        self.duplicates.update_application_status(application_id, status, bitrix_deal_id)
