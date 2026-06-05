from datetime import datetime, timedelta
from uuid import uuid4

from app.db.models import Base, OperatorTicket
from app.db.session import SessionLocal, engine
from app.services.operator_ticket_service import OperatorTicketService, TicketPayload
from app.workers.sla_worker import run_sla_checks


def setup_module():
    Base.metadata.create_all(bind=engine)


def _payload(request_id: str, deal_id: int, reason: str = "policy_status_request") -> TicketPayload:
    return TicketPayload(
        request_id=request_id,
        telegram_user_id=5982080132,
        telegram_chat_id=5982080132,
        bitrix_deal_id=deal_id,
        reason=reason,
        client_name="",
        client_phone="",
        preferred_language="ru",
        vehicle_type="OC graniczne (border insurance)",
        license_plate="AM***AB",
        vin="",
        insurance_period_days=30,
        insurance_start_date="2026-07-20",
        comment="client asks where policy is",
    )


def test_create_or_get_ticket_deduplicates_open_deal_reason():
    svc = OperatorTicketService()
    suffix = uuid4().hex[:8]
    deal_id = int("525" + suffix[:5], 16)
    first, first_created = svc.create_or_get_ticket(_payload(f"OP-TEST-1-{suffix}", deal_id))
    second, second_created = svc.create_or_get_ticket(_payload(f"OP-TEST-2-{suffix}", deal_id))

    assert first_created is True
    assert second_created is False
    assert second.request_id == first.request_id
    assert first.priority == "high"
    assert first.sla_due_at is not None


def test_take_ticket_assigns_once():
    svc = OperatorTicketService()
    request_id = f"OP-TEST-TAKE-{uuid4().hex[:8]}"
    svc.create_ticket(_payload(request_id, 52582, "client_requested_operator"))

    assert svc.take_ticket(request_id, 1001) == (True, "taken")
    assert svc.take_ticket(request_id, 2002) == (False, "already_assigned")


def test_get_active_by_user_prefers_ticket_waiting_for_client_reply():
    svc = OperatorTicketService()
    suffix = uuid4().hex[:8]
    telegram_user_id = int("598" + suffix[:7], 16)
    waiting_request_id = f"OP-TEST-WAITING-{suffix}"
    newer_request_id = f"OP-TEST-NEWER-{suffix}"

    waiting_payload = _payload(waiting_request_id, 52600, "client_requested_operator")
    waiting_payload.telegram_user_id = telegram_user_id
    waiting_payload.telegram_chat_id = telegram_user_id
    svc.create_ticket(waiting_payload)
    assert svc.take_ticket(waiting_request_id, 470919281) == (True, "taken")
    assert svc.set_status(waiting_request_id, "waiting_client") is True

    newer_payload = _payload(newer_request_id, 52601, "policy_status_request")
    newer_payload.telegram_user_id = telegram_user_id
    newer_payload.telegram_chat_id = telegram_user_id
    svc.create_ticket(newer_payload)

    ticket = svc.get_active_by_user(telegram_user_id)

    assert ticket is not None
    assert ticket.request_id == waiting_request_id
    assert ticket.operator_id == 470919281


def test_sla_worker_uses_sla_due_at(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "app.services.operator_notifier_service.OperatorNotifierService.notify_new_ticket",
        lambda self, text: calls.append(text),
    )
    with SessionLocal() as db:
        db.merge(
            OperatorTicket(
                request_id=f"OP-TEST-SLA-{uuid4().hex[:8]}",
                telegram_user_id=3,
                status="waiting_operator",
                created_at=datetime.utcnow() - timedelta(minutes=1),
                sla_due_at=datetime.utcnow() - timedelta(minutes=1),
                sla_breach=False,
            )
        )
        db.commit()

    result = run_sla_checks()

    assert result["sla_breaches"] >= 1
    assert calls


def test_transfer_ticket_preserves_status_and_logs_history():
    svc = OperatorTicketService()
    request_id = f"OP-TEST-TRANSFER-{uuid4().hex[:8]}"
    svc.create_ticket(_payload(request_id, 52583, "client_requested_operator"))
    assert svc.take_ticket(request_id, 1001) == (True, "taken")

    ok, reason, ticket = svc.transfer_ticket(
        request_id,
        from_operator_id=1001,
        to_operator_id=2002,
        reason="Конец смены",
    )

    assert ok is True
    assert reason == "transferred"
    assert ticket.operator_id == 2002
    assert ticket.previous_operator_id == 1001
    assert ticket.status == "in_progress"
    transfers = svc.list_transfers(request_id)
    assert transfers[0].from_operator_id == 1001
    assert transfers[0].to_operator_id == 2002
    assert transfers[0].reason == "Конец смены"


def test_internal_comments_store_pinned_context():
    svc = OperatorTicketService()
    request_id = f"OP-TEST-COMMENT-{uuid4().hex[:8]}"
    svc.create_ticket(_payload(request_id, 52584, "client_requested_operator"))

    comment = svc.add_internal_comment(
        request_id,
        operator_id=1001,
        comment_text="Не отправлять до подтверждения оплаты.",
        comment_type="warning",
        is_pinned=True,
    )

    assert comment is not None
    assert comment.is_pinned is True
    pinned = svc.pinned_internal_comments(request_id)
    assert pinned[0].comment_text == "Не отправлять до подтверждения оплаты."
