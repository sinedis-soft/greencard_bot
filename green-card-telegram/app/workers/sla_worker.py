from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import OperatorTicket
from app.db.session import SessionLocal
from app.services.analytics_service import AnalyticsService
from app.services.operator_notifier_service import ClientNotifierService, OperatorNotifierService


def run_sla_checks() -> dict:
    now = datetime.utcnow()
    changed = 0
    reminded_clients = 0
    with SessionLocal() as db:
        overdue = list(db.scalars(select(OperatorTicket).where(OperatorTicket.status == "new", OperatorTicket.created_at <= now - timedelta(minutes=10), OperatorTicket.sla_breach == False)))
        for t in overdue:
            t.sla_breach = True
            t.reminder_sent_at = now
            OperatorNotifierService().notify_new_ticket(f"SLA breached: {t.request_id}")
            AnalyticsService().track("sla_breach", request_id=t.request_id, telegram_user_id=t.telegram_user_id)
            AnalyticsService().track("operator_reminder_sent", request_id=t.request_id, telegram_user_id=t.telegram_user_id)
            changed += 1

        stale_clients = list(db.scalars(select(OperatorTicket).where(OperatorTicket.status == "new", OperatorTicket.last_client_message_at != None, OperatorTicket.last_client_message_at <= now - timedelta(minutes=15), OperatorTicket.reminder_sent_at == None)))
        for t in stale_clients:
            if t.telegram_user_id:
                ClientNotifierService().send_to_client(t.telegram_user_id, "Reminder: please complete your application")
            t.reminder_sent_at = now
            AnalyticsService().track("application_reminder_sent", request_id=t.request_id, telegram_user_id=t.telegram_user_id)
            reminded_clients += 1
        db.commit()
    return {"sla_breaches": changed, "client_reminders": reminded_clients}
