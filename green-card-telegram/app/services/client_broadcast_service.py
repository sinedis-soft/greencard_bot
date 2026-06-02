from sqlalchemy import select

from app.db.models import AnalyticsEvent, Application, Base, OperatorTicket
from app.db.session import SessionLocal, engine
from app.services.operator_notifier_service import ClientNotifierService

RESTART_NOTICE_TEXT = "MAJOR CHANGES HAVE BEEN APPLIED. PLEASE RESTART THIS CHAT BOT."


class ClientBroadcastService:
    def __init__(self) -> None:
        Base.metadata.create_all(bind=engine)

    def known_telegram_user_ids(self) -> list[int]:
        user_ids: set[int] = set()
        with SessionLocal() as db:
            for model in (Application, OperatorTicket, AnalyticsEvent):
                rows = db.scalars(
                    select(model.telegram_user_id).where(
                        model.telegram_user_id.is_not(None)
                    )
                )
                user_ids.update(int(user_id) for user_id in rows if user_id)
        return sorted(user_ids)

    def send_restart_notice(self) -> dict[str, int]:
        notifier = ClientNotifierService()
        sent = 0
        failed = 0
        for user_id in self.known_telegram_user_ids():
            if notifier.send_restart_notice(user_id, RESTART_NOTICE_TEXT):
                sent += 1
            else:
                failed += 1
        return {"sent": sent, "failed": failed}
