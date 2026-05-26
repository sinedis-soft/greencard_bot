from datetime import datetime, timedelta

from app.db.models import Base, OperatorTicket
from app.db.session import engine, SessionLocal
from app.workers.sla_worker import run_sla_checks


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_ticket_gets_sla_breach(monkeypatch):
    calls = []
    monkeypatch.setattr("app.services.operator_notifier_service.OperatorNotifierService.notify_new_ticket", lambda self, text: calls.append(text))
    with SessionLocal() as db:
        db.merge(OperatorTicket(request_id="r1", telegram_user_id=1, status="new", created_at=datetime.utcnow()-timedelta(minutes=11)))
        db.commit()
    result = run_sla_checks()
    assert result["sla_breaches"] >= 1
    assert calls


def test_client_gets_only_one_reminder(monkeypatch):
    sent = []
    monkeypatch.setattr("app.services.operator_notifier_service.ClientNotifierService.send_to_client", lambda self, uid, text: sent.append((uid, text)))
    rid = "r2"
    with SessionLocal() as db:
        db.merge(OperatorTicket(request_id=rid, telegram_user_id=2, status="new", last_client_message_at=datetime.utcnow()-timedelta(minutes=16), reminder_sent_at=None))
        db.commit()
    run_sla_checks()
    run_sla_checks()
    assert len([x for x in sent if x[0] == 2]) == 1
