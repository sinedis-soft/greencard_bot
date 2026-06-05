from pathlib import Path

from app.bots.client_bot.env import bitrix_webhook_fallback_envs, resolve_env_value


def test_resolve_env_value_uses_primary_before_fallback(monkeypatch):
    monkeypatch.setenv("PRIMARY_WEBHOOK", "https://primary.example/rest/1/token")
    monkeypatch.setenv("FALLBACK_WEBHOOK", "https://fallback.example/rest/1/token")

    assert (
        resolve_env_value("PRIMARY_WEBHOOK", ("FALLBACK_WEBHOOK",), "default")
        == "https://primary.example/rest/1/token"
    )


def test_resolve_env_value_uses_fallback_alias(monkeypatch):
    monkeypatch.delenv("EUROPOLIS_BITRIX24_WEBHOOK_URL", raising=False)
    monkeypatch.setenv(
        "EUROPOLIS_BITRIX_WEBHOOK_URL", "https://europolis.example/rest/7/token"
    )

    assert (
        resolve_env_value(
            "EUROPOLIS_BITRIX24_WEBHOOK_URL",
            bitrix_webhook_fallback_envs("EUROPOLIS_BITRIX24_WEBHOOK_URL"),
            "default",
        )
        == "https://europolis.example/rest/7/token"
    )


def test_europolis_bitrix_fallback_envs_keep_common_webhook_last():
    fallback_envs = bitrix_webhook_fallback_envs("EUROPOLIS_BITRIX24_WEBHOOK_URL")

    assert "EUROPOLIS_BITRIX_WEBHOOK_URL" in fallback_envs
    assert fallback_envs[-1] == "BITRIX24_WEBHOOK_URL"


def test_europolis_bot_uses_own_tariffs_and_calculator_vehicle_types():
    source = Path("app/bots/europolis_client_bot/bot.py").read_text()

    assert 'tariffs_file="europolis_tariffs.yaml"' in source
    assert (
        'calculator_vehicle_types=("car", "van", "truck", "trailer", "special")'
        in source
    )


def test_europolis_tariffs_match_requested_price_table():
    source = Path("app/config/europolis_tariffs.yaml").read_text()

    assert 'currency: "EUR"' in source
    assert 'currency_symbol: "€"' in source
    assert (
        '  car:\n    "30": 54.17\n    "60": 104.17\n    "90": 150\n'
        '    "180": 265.5\n    "365": 500'
        in source
    )
    assert (
        '  van:\n    "30": 541.67\n    "60": 1041.67\n    "90": 1500\n'
        '    "180": 2625\n    "365": 5000'
        in source
    )
    assert (
        '  truck:\n    "30": 100\n    "60": 200\n    "90": 300\n'
        '    "180": 0\n    "365": 0'
        in source
    )


def test_calculator_apply_callback_uses_callback_user_for_application_start():
    source = Path("app/bots/client_bot/handlers/calculator.py").read_text()

    assert "await send_apply(callback.message, state, user=callback.from_user)" in source


def test_apply_menu_shortcut_accepts_all_main_menu_button_prefixes():
    source = Path("app/bots/client_bot/handlers/apply.py").read_text()

    for prefix in ("🧮", "❓", "🌍", "📝", "📄", "💳", "👨‍💼", "🌐"):
        assert prefix in source


def test_calculator_followup_reminder_gets_apply_button_context():
    calculator_source = Path("app/bots/client_bot/handlers/calculator.py").read_text()
    reminder_source = Path("app/services/reminder_service.py").read_text()

    assert (
        'client_bot=getattr(callback.bot, "client_bot_code", "default")'
        in calculator_source
    )
    assert (
        'apply_button_text=i18n.get_text(lang, "calculator.apply_cta")'
        in calculator_source
    )
    assert '"callback_data": "calc:apply"' in reminder_source
    assert '"apply_button_text"' in reminder_source
