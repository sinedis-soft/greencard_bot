import sys
import types

requests_stub = types.SimpleNamespace(post=lambda *args, **kwargs: None)
sys.modules.setdefault("requests", requests_stub)

from app.services.operator_notifier_service import OperatorNotifierService


def test_operator_notifier_sends_ticket_text_and_copyable_reply_command(monkeypatch):
    calls = []

    monkeypatch.setenv("OPERATOR_BOT_TOKEN", "token")
    monkeypatch.setenv("OPERATOR_IDS", "100,200")
    monkeypatch.setattr(
        "app.services.operator_notifier_service.requests.post",
        lambda url, json, timeout: calls.append((url, json, timeout)),
    )

    OperatorNotifierService().notify_new_ticket("ticket text", "/reply ticket-1")

    assert calls == [
        ("https://api.telegram.org/bottoken/sendMessage", {"chat_id": 100, "text": "ticket text"}, 5),
        ("https://api.telegram.org/bottoken/sendMessage", {"chat_id": 100, "text": "/reply ticket-1"}, 5),
        ("https://api.telegram.org/bottoken/sendMessage", {"chat_id": 200, "text": "ticket text"}, 5),
        ("https://api.telegram.org/bottoken/sendMessage", {"chat_id": 200, "text": "/reply ticket-1"}, 5),
    ]


def test_operator_notifier_keeps_single_message_when_reply_command_is_absent(monkeypatch):
    calls = []

    monkeypatch.setenv("OPERATOR_BOT_TOKEN", "token")
    monkeypatch.setenv("OPERATOR_IDS", "100")
    monkeypatch.setattr(
        "app.services.operator_notifier_service.requests.post",
        lambda url, json, timeout: calls.append((url, json, timeout)),
    )

    OperatorNotifierService().notify_new_ticket("SLA breached: ticket-1")

    assert calls == [
        ("https://api.telegram.org/bottoken/sendMessage", {"chat_id": 100, "text": "SLA breached: ticket-1"}, 5),
    ]
