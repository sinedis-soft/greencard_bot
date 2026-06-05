from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import OperatorTicket
from app.db.session import SessionLocal
from app.services.analytics_service import AnalyticsService
from app.services.operator_message_formatter import (
    operator_client_bot_line,
    operator_language_line,
)
from app.services.operator_notifier_service import ClientNotifierService, OperatorNotifierService

SLA_ACTIVE_STATUSES = ("new", "waiting_operator", "in_progress")


def run_sla_checks() -> dict:
    now = datetime.utcnow()
    changed = 0
    reminded_clients = 0
    with SessionLocal() as db:
        overdue = list(
            db.scalars(
                select(OperatorTicket).where(
                    OperatorTicket.status.in_(SLA_ACTIVE_STATUSES),
                    OperatorTicket.sla_breach == False,
                    (
                        (OperatorTicket.sla_due_at != None) & (OperatorTicket.sla_due_at <= now)
                    )
                    | (
                        (OperatorTicket.sla_due_at == None)
                        & (OperatorTicket.created_at <= now - timedelta(minutes=10))
                    ),
                )
            )
        )
        for t in overdue:
            t.sla_breach = True
            t.reminder_sent_at = now
            OperatorNotifierService().notify_new_ticket(
                f"SLA breached: {t.request_id}\n"
                f"{operator_client_bot_line(t.client_bot)}\n"
                f"{operator_language_line(t.preferred_language)}"
            )
            AnalyticsService().track("sla_breach", request_id=t.request_id, telegram_user_id=t.telegram_user_id)
            AnalyticsService().track("operator_reminder_sent", request_id=t.request_id, telegram_user_id=t.telegram_user_id)
            changed += 1

        stale_clients = list(
            db.scalars(
                select(OperatorTicket).where(
                    OperatorTicket.status == "new",
                    OperatorTicket.last_client_message_at != None,
                    OperatorTicket.last_client_message_at <= now - timedelta(minutes=15),
                    OperatorTicket.reminder_sent_at == None,
                )
            )
        )
        for t in stale_clients:
            if t.telegram_user_id:
                ClientNotifierService().send_to_client(
                    t.telegram_user_id,
                    "Reminder: please complete your application",
                    client_bot=t.client_bot,
                )

            t.reminder_sent_at = now
            AnalyticsService().track("application_reminder_sent", request_id=t.request_id, telegram_user_id=t.telegram_user_id)
            reminded_clients += 1
        db.commit()
    return {"sla_breaches": changed, "client_reminders": reminded_clients}
