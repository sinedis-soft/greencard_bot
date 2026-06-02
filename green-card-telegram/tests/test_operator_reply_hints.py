import sys
import types

requests_stub = types.SimpleNamespace(post=lambda *args, **kwargs: None)
sys.modules.setdefault("requests", requests_stub)

from app.services.operator_notifier_service import (
    ClientNotifierService,
    OperatorNotifierService,
)


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


def test_client_notifier_restart_notice_includes_start_button(monkeypatch):
    calls = []

    monkeypatch.setenv("BOT_TOKEN", "client-token")
    monkeypatch.setattr(
        "app.services.operator_notifier_service.requests.post",
        lambda url, json, timeout: calls.append((url, json, timeout)),
    )

    assert ClientNotifierService().send_restart_notice(12345, "restart please") is True

    assert calls == [
        (
            "https://api.telegram.org/botclient-token/sendMessage",
            {
                "chat_id": 12345,
                "text": "restart please",
                "reply_markup": {
                    "keyboard": [[{"text": "/start"}]],
                    "resize_keyboard": True,
                },
            },
            5,
        )
    ]



def test_operator_notifier_reply_sent_skips_replying_operator(monkeypatch):
    calls = []

    monkeypatch.setenv("OPERATOR_BOT_TOKEN", "token")
    monkeypatch.setenv("OPERATOR_IDS", "100,200,300")
    monkeypatch.setattr(
        "app.services.operator_notifier_service.requests.post",
        lambda url, json, timeout: calls.append((url, json, timeout)),
    )

    OperatorNotifierService().notify_operator_reply_sent(
        "Клиенту @client ответил на request_id r1 оператор @operator",
        exclude_operator_id=200,
    )

    assert calls == [
        (
            "https://api.telegram.org/bottoken/sendMessage",
            {
                "chat_id": 100,
                "text": "Клиенту @client ответил на request_id r1 оператор @operator",
            },
            5,
        ),
        (
            "https://api.telegram.org/bottoken/sendMessage",
            {
                "chat_id": 300,
                "text": "Клиенту @client ответил на request_id r1 оператор @operator",
            },
            5,
        ),
    ]

