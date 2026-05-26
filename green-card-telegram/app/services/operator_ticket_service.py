from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select

from app.db.models import Base, OperatorActionLog, OperatorTicket
from app.db.session import SessionLocal, engine


@dataclass
class TicketPayload:
    request_id: str
    telegram_user_id: int | None
    client_name: str
    client_phone: str
    preferred_language: str
    vehicle_type: str
    license_plate: str
    vin: str
    insurance_period_days: int
    insurance_start_date: str
    comment: str


class OperatorTicketService:
    def __init__(self) -> None:
        Base.metadata.create_all(bind=engine)

    def create_ticket(self, data: TicketPayload) -> None:
        with SessionLocal() as db:
            payload = data.__dict__.copy()
            payload.setdefault("first_response_deadline", datetime.utcnow() + timedelta(minutes=10))
            payload.setdefault("last_client_message_at", datetime.utcnow())
            db.merge(OperatorTicket(**payload))
            db.commit()

    def list_new(self) -> list[OperatorTicket]:
        with SessionLocal() as db:
            return list(db.scalars(select(OperatorTicket).where(OperatorTicket.status == "new").order_by(OperatorTicket.created_at.asc())))

    def set_status(self, request_id: str, status: str) -> bool:
        with SessionLocal() as db:
            ticket = db.get(OperatorTicket, request_id)
            if not ticket:
                return False
            ticket.status = status
            db.commit()
            return True

    def get_ticket(self, request_id: str) -> OperatorTicket | None:
        with SessionLocal() as db:
            return db.get(OperatorTicket, request_id)

    def log_action(self, request_id: str, operator_id: int, action: str, message: str = "") -> None:
        with SessionLocal() as db:
            db.add(OperatorActionLog(request_id=request_id, operator_id=operator_id, action=action, message=message))
            db.commit()
