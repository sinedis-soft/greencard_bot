from app.bots.operator_bot.command_menu import OPERATOR_COMMANDS, operator_help_text


def test_operator_command_menu_includes_help_first():
    assert OPERATOR_COMMANDS[0] == ("help", "Показать доступные команды")
    assert {command for command, _ in OPERATOR_COMMANDS} >= {
        "help",
        "tickets",
        "reply",
        "done",
        "take",
        "close",
        "restart_bot",
    }


def test_operator_help_text_lists_clickable_commands_and_reply_examples():
    text = operator_help_text()

    assert text.startswith("🆘 Помощь оператора")
    assert "/help — показать эту подсказку." in text
    assert "/tickets — открыть очередь заявок" in text
    assert "/reply <request_id> <текст>" in text
    assert "/reply <request_id> — начать отправку файла/полиса клиенту." in text
    assert "Нажмите команду" in text
    assert "Как открыть меню быстрых ответов:" in text
    assert "Нажмите «Шаблоны», чтобы отправить быстрый ответ клиенту" in text
    assert "app/operator_templates/templates.yaml" in text
    assert "SENIOR_OPERATOR_IDS/ADMIN_OPERATOR_IDS" in text
