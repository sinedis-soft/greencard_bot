from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import requests
from sqlalchemy import select

from app.db.models import NotificationDeduplication, NotificationLog, NotificationRule, NotificationTemplate
from app.db.session import SessionLocal
from app.services.operator_notifier_service import ClientNotifierService
from app.services.operator_service import OperatorService

NOTIFICATION_CHANNELS = {"client_telegram", "operator_telegram", "admin_telegram", "bitrix_comment", "email"}

DEFAULT_NOTIFICATION_TEMPLATES: dict[tuple[str, str, str], str] = {
    ("application_accepted", "client", "ru"): "Заявка принята.\n\nНомер: {request_id}\nСтатус: {public_status}\n\nМы сообщим вам, когда будет следующий шаг.",
    ("documents_required", "client", "ru"): "По заявке {request_id} нужны дополнительные документы:\n\n{document_list}\n\nПожалуйста, загрузите их в этом чате.",
    ("waiting_payment", "client", "ru"): "По заявке {request_id} ожидается оплата.\n\nСумма: {amount} {currency}\n\nПосле оплаты загрузите подтверждение платежа.",
    ("payment_received", "client", "ru"): "Оплата по заявке {request_id} получена.\n\nПолис передан на оформление.",
    ("policy_ready", "client", "ru"): "Полис по заявке {request_id} готов.\n\nВы можете получить его в Telegram.",
    ("policy_sent", "client", "ru"): "Полис по заявке {request_id} отправлен.\n\nПроверьте файл в этом чате.",
    ("policy_expiring_soon", "client", "ru"): "Полис по автомобилю {vehicle_plate_masked} заканчивается {end_date}.\n\nХотите оформить новый?",
    ("policy_expires_3_days", "client", "ru"): "Полис по автомобилю {vehicle_plate_masked} заканчивается {end_date}.\n\nХотите оформить новый?",
    ("policy_expires_today", "client", "ru"): "Полис по автомобилю {vehicle_plate_masked} заканчивается сегодня.\n\nХотите оформить новый полис?",
    ("calculator_followup", "client", "ru"): "Вы рассчитывали стоимость OC graniczne (border insurance).\n\nТип ТС: {vehicle_type}\nСрок: {period_days} дней\nПредварительная стоимость: {estimated_price} {currency}\n\nПродолжить оформление?",
    ("draft_30_minutes", "client", "ru"): "Вы начали оформление OC graniczne (border insurance), но не завершили заявку.\n\nХотите продолжить?",
    ("draft_24_hours", "client", "ru"): "Ваша заявка на OC graniczne (border insurance) ещё не завершена.\n\nЕсли полис всё ещё нужен, вы можете продолжить оформление.",
    ("draft_close_3_days", "client", "ru"): "Черновик заявки закрыт, так как оформление не было завершено.\n\nЕсли полис всё ещё нужен, создайте новую заявку.",
    ("operator_new_application", "operator", "ru"): "Новая заявка\n\nНомер: {request_id}\nПродукт: {product_type}\nАвто: {vehicle_plate_masked}\nЯзык: {language}\nИсточник: {source_channel}",
    ("operator_client_message", "operator", "ru"): "Клиент ответил по тикету {ticket_id}\n\nЗаявка: {request_id}\nСообщение: {message_preview}",
    ("operator_payment_uploaded", "operator", "ru"): "Клиент загрузил подтверждение оплаты.\n\nЗаявка: {request_id}\nАвто: {vehicle_plate_masked}\nСделка Bitrix: {bitrix_deal_id}\n\nФайл прикреплён к сделке.",
    ("operator_sla_breached", "operator", "ru"): "SLA просрочен\n\nТикет: {ticket_id}\nЗаявка: {request_id}\nПричина: {reason}\nПросрочка: {delay_minutes} мин\nОператор: {assigned_operator_name}",
    ("operator_bitrix_failed", "operator", "ru"): "Bitrix не принял заявку.\n\nЗаявка: {request_id}\nОшибка: {error_code}\nПопыток: {attempts}\n\nОткройте карточку и повторите синхронизацию.",
    ("operator_policy_requested", "operator", "ru"): "Клиент запросил полис\n\nЗаявка: {request_id}\nСделка Bitrix: {bitrix_deal_id}\nСтатус полиса: {policy_status}\nФайл полиса: отсутствует",
    ("admin_worker_down", "admin", "ru"): "Worker не отвечает\n\nСервис: {worker_name}\nПоследний heartbeat: {last_seen_at}\n\nПроверьте контейнер.",
    ("admin_bitrix_error", "admin", "ru"): "Проблема с Bitrix API\n\nОшибок за 10 минут: {error_count}\nПоследняя ошибка: {last_error_code}\n\nПроверьте webhook/token/API.",
    ("admin_redis_queue_high", "admin", "ru"): "Очередь Redis растёт\n\nОчередь: {queue_name}\nЗадач: {queue_size}\nСтарейшая задача: {oldest_job_age_minutes} мин",
    ("admin_disk_space_low", "admin", "ru"): "Мало места на диске\n\nСвободно: {free_percent}%\nПуть: {path}",
}

DEFAULT_RULE_THROTTLES = {
    "admin_bitrix_error": 600,
    "admin_disk_space_low": 1800,
    "admin_redis_queue_high": 600,
    "admin_worker_down": 600,
    "operator_sla_breached": 300,
}


@dataclass(frozen=True)
class NotificationResult:
    status: str
    event_key: str
    recipient_type: str
    recipient_id: str | None
    channel: str
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class NotificationService:
    def send(
        self,
        event_key: str,
        recipient_type: str,
        recipient_id: str | None,
        channel: str,
        language: str = "ru",
        context: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
        reply_markup: dict[str, Any] | None = None,
        client_bot: str | None = None,
    ) -> NotificationResult:
        context = self._safe_context(context or {})
        if channel not in NOTIFICATION_CHANNELS:
            result = NotificationResult("skipped", event_key, recipient_type, recipient_id, channel, "unsupported_channel")
            self._log(result, context)
            return result

        rule = self._get_rule(event_key, recipient_type, channel)
        if rule and not rule.is_enabled:
            result = NotificationResult("skipped", event_key, recipient_type, recipient_id, channel, "rule_disabled")
            self._log(result, context)
            return result

        throttle = rule.throttle_seconds if rule else DEFAULT_RULE_THROTTLES.get(event_key, 0)
        if dedupe_key and not self.should_send_notification(event_key, recipient_id or "", dedupe_key, throttle):
            result = NotificationResult("skipped", event_key, recipient_type, recipient_id, channel, "deduplicated")
            self._log(result, context)
            return result

        template = self._get_template(event_key, recipient_type, language)
        if not template:
            result = NotificationResult("skipped", event_key, recipient_type, recipient_id, channel, "template_not_found")
            self._log(result, context)
            return result

        body = self.render_template(template, context)
        try:
            self._send_to_channel(channel, recipient_id, body, reply_markup, client_bot)
            if dedupe_key:
                self._remember_dedupe(event_key, recipient_id or "", dedupe_key)
            result = NotificationResult("sent", event_key, recipient_type, recipient_id, channel)
            self._log(result, context)
            return result
        except Exception as exc:
            result = NotificationResult("failed", event_key, recipient_type, recipient_id, channel, str(exc))
            self._log(result, context)
            return result

    def should_send_notification(self, event_key: str, recipient_id: str, dedupe_key: str, throttle_seconds: int) -> bool:
        if throttle_seconds <= 0:
            return True
        cutoff = datetime.utcnow() - timedelta(seconds=throttle_seconds)
        with SessionLocal() as db:
            existing = db.scalar(
                select(NotificationDeduplication).where(
                    NotificationDeduplication.event_key == event_key,
                    NotificationDeduplication.recipient_id == recipient_id,
                    NotificationDeduplication.dedupe_key == dedupe_key,
                    NotificationDeduplication.sent_at >= cutoff,
                )
            )
            return existing is None

    def _get_rule(self, event_key: str, recipient_type: str, channel: str) -> NotificationRule | None:
        with SessionLocal() as db:
            rule = db.scalar(
                select(NotificationRule)
                .where(
                    NotificationRule.event_key == event_key,
                    NotificationRule.recipient_type == recipient_type,
                    NotificationRule.channel == channel,
                )
                .order_by(NotificationRule.created_at.desc())
            )
            if rule:
                db.expunge(rule)
            return rule

    def _get_template(self, event_key: str, recipient_type: str, language: str) -> str | None:
        languages = (language, "ru", "en") if language not in {"ru", "en"} else (language, "ru" if language != "ru" else "en")
        with SessionLocal() as db:
            for lang in languages:
                template = db.scalar(
                    select(NotificationTemplate)
                    .where(
                        NotificationTemplate.event_key == event_key,
                        NotificationTemplate.recipient_type == recipient_type,
                        NotificationTemplate.language == lang,
                        NotificationTemplate.is_active == True,
                    )
                    .order_by(NotificationTemplate.updated_at.desc())
                )
                if template:
                    return template.body
                default = DEFAULT_NOTIFICATION_TEMPLATES.get((event_key, recipient_type, lang))
                if default:
                    return default
        return None

    @staticmethod
    def render_template(template: str, context: dict[str, Any]) -> str:
        safe_context = {key: ("" if value is None else value) for key, value in context.items()}
        try:
            return template.format(**safe_context)
        except KeyError:
            return template

    def _send_to_channel(
        self,
        channel: str,
        recipient_id: str | None,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        client_bot: str | None = None,
    ) -> None:
        if channel == "client_telegram":
            if not recipient_id:
                raise RuntimeError("recipient_id_required")
            sent = ClientNotifierService().send_to_client(
                int(recipient_id),
                text,
                reply_markup=reply_markup,
                client_bot=client_bot,
            )
            if not sent:
                raise RuntimeError("telegram_send_failed")
        elif channel == "operator_telegram":
            self._send_operator_telegram(recipient_id, text)
        elif channel == "admin_telegram":
            self._send_admin_telegram(recipient_id, text)
        elif channel in {"bitrix_comment", "email"}:
            # MVP: log-only channel until Bitrix timeline/email clients are configured.
            return

    def _send_operator_telegram(self, recipient_id: str | None, text: str) -> None:
        token = os.getenv("OPERATOR_BOT_TOKEN", "")
        if recipient_id and recipient_id != "broadcast":
            self._send_telegram(token, recipient_id, text)
            return
        for operator_id in OperatorService().active_operator_ids():
            self._send_telegram(token, str(operator_id), text)

    def _send_admin_telegram(self, recipient_id: str | None, text: str) -> None:
        token = os.getenv("ADMIN_BOT_TOKEN") or os.getenv("OPERATOR_BOT_TOKEN", "")
        ids = [recipient_id] if recipient_id and recipient_id != "broadcast" else [str(item) for item in OperatorService().privileged_operator_ids()]
        for admin_id in ids:
            self._send_telegram(token, admin_id, text)

    @staticmethod
    def _send_telegram(token: str, recipient_id: str | None, text: str) -> None:
        if not token:
            raise RuntimeError("telegram_token_not_configured")
        if not recipient_id:
            raise RuntimeError("recipient_id_required")
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": int(recipient_id), "text": text},
            timeout=5,
        )
        if getattr(response, "ok", True) is False:
            raise RuntimeError("telegram_send_failed")

    def _remember_dedupe(self, event_key: str, recipient_id: str, dedupe_key: str) -> None:
        with SessionLocal() as db:
            db.add(NotificationDeduplication(event_key=event_key, recipient_id=recipient_id, dedupe_key=dedupe_key))
            db.commit()

    def _log(self, result: NotificationResult, context: dict[str, Any]) -> None:
        with SessionLocal() as db:
            db.add(
                NotificationLog(
                    event_key=result.event_key,
                    recipient_type=result.recipient_type,
                    recipient_id=result.recipient_id,
                    channel=result.channel,
                    status=result.status,
                    error_message=result.error_message,
                    context_json=json.dumps(context, ensure_ascii=False),
                    sent_at=datetime.utcnow() if result.status == "sent" else None,
                )
            )
            db.commit()

    @staticmethod
    def _safe_context(context: dict[str, Any]) -> dict[str, Any]:
        blocked_keys = {"passport", "passport_series_number", "vin", "phone", "email", "full_vin"}
        return {key: value for key, value in context.items() if key not in blocked_keys}
