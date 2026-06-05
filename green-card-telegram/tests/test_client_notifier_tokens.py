import sys
import types

requests_stub = types.SimpleNamespace(post=lambda *args, **kwargs: None)
sys.modules.setdefault("requests", requests_stub)

from app.services.operator_notifier_service import ClientNotifierService


def test_client_notifier_uses_europolis_token(monkeypatch):
    calls = []

    monkeypatch.setenv("BOT_TOKEN", "default-token")
    monkeypatch.setenv("EUROPOLIS_BOT_TOKEN", "europolis-token")

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))

        class Response:
            ok = True

        return Response()

    monkeypatch.setattr(
        "app.services.operator_notifier_service.requests.post", fake_post
    )

    sent = ClientNotifierService().send_to_client(123, "hello", client_bot="europolis")

    assert sent is True
    assert calls[0][0] == "https://api.telegram.org/boteuropolis-token/sendMessage"


def test_client_notifier_uses_default_token(monkeypatch):
    calls = []

    monkeypatch.setenv("BOT_TOKEN", "default-token")
    monkeypatch.delenv("EUROPOLIS_BOT_TOKEN", raising=False)

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))

        class Response:
            ok = True

        return Response()

    monkeypatch.setattr(
        "app.services.operator_notifier_service.requests.post", fake_post
    )

    sent = ClientNotifierService().send_to_client(123, "hello", client_bot="default")

    assert sent is True
    assert calls[0][0] == "https://api.telegram.org/botdefault-token/sendMessage"


def test_client_notifier_sends_inline_apply_markup(monkeypatch):
    calls = []

    monkeypatch.setenv("BOT_TOKEN", "default-token")

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))

        class Response:
            ok = True

        return Response()

    monkeypatch.setattr("app.services.operator_notifier_service.requests.post", fake_post)

    reply_markup = {
        "inline_keyboard": [[{"text": "📝 Оформить", "callback_data": "calc:apply"}]]
    }
    sent = ClientNotifierService().send_to_client(
        123, "reminder", reply_markup=reply_markup, client_bot="default"
    )

    assert sent is True
    assert calls[0][1]["json"]["reply_markup"] == reply_markup
