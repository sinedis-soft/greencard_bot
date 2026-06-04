from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def reply_instruction(request_id: str) -> str:
    return f"Ответ клиенту: отправьте ваш текст после команды /reply {request_id}"


def reply_command(request_id: str) -> str:
    return f"/reply {request_id}"


def ticket_actions_keyboard(request_id: str, bitrix_url: str = "") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Взять", callback_data=f"tq:take:{request_id}")
    b.button(text="Ответить", callback_data=f"tq:reply:{request_id}")
    b.button(text="Шаблоны", callback_data=f"tq:templates:{request_id}")
    b.button(text="Передать оператору", callback_data=f"tq:transfer:{request_id}")
    b.button(text="Комментарий", callback_data=f"tq:comment:{request_id}")
    b.button(text="Все комментарии", callback_data=f"tq:comments:{request_id}")
    b.button(text="Запросить документ", callback_data=f"tq:doc:{request_id}")
    b.button(text="Запросить оплату", callback_data=f"tq:pay:{request_id}")
    if bitrix_url:
        b.button(text="Открыть в Bitrix", url=bitrix_url)
    b.button(text="Закрыть", callback_data=f"tq:close:{request_id}:resolved")
    b.adjust(2, 2, 2, 1, 1)
    return b.as_markup()


def ticket_queue_keyboard() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Новые", callback_data="tq:list:new")
    b.button(text="Мои в работе", callback_data="tq:list:mine")
    b.button(text="Клиент ждёт", callback_data="tq:list:waiting_operator")
    b.button(text="SLA", callback_data="tq:list:sla")
    b.button(text="Ошибки Bitrix", callback_data="tq:list:bitrix_errors")
    b.button(text="Ожидают клиента", callback_data="tq:list:waiting_client")
    b.adjust(2, 2, 2)
    return b.as_markup()


def ticket_list_item_keyboard(request_id: str, bitrix_url: str = "") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Открыть", callback_data=f"tq:open:{request_id}")
    b.button(text="Взять", callback_data=f"tq:take:{request_id}")
    if bitrix_url:
        b.button(text="Bitrix", url=bitrix_url)
    b.adjust(2, 1)
    return b.as_markup()


def ticket_templates_keyboard(request_id: str, templates) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for template in templates:
        b.button(text=template.title, callback_data=f"tq:tpl:{request_id}:{template.key}")
    b.adjust(1)
    return b.as_markup()


def ticket_template_preview_keyboard(request_id: str, template_key: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="Отправить", callback_data=f"tq:tplsend:{request_id}:{template_key}")
    b.button(text="Изменить текст", callback_data=f"tq:reply:{request_id}")
    b.button(text="Отмена", callback_data=f"tq:open:{request_id}")
    b.adjust(1)
    return b.as_markup()


def ticket_close_keyboard(request_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    reasons = [
        ("Вопрос решён", "resolved"),
        ("Клиент не отвечает", "client_no_response"),
        ("Дубль", "duplicate"),
        ("Ошибочный тикет", "wrong_ticket"),
        ("Передано в Bitrix", "moved_to_bitrix"),
    ]
    for title, key in reasons:
        b.button(text=title, callback_data=f"tq:close:{request_id}:{key}")
    b.adjust(1)
    return b.as_markup()

def ticket_transfer_operator_keyboard(request_id: str, operator_ids: list[int], current_operator_id: int | None) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for operator_id in operator_ids:
        if operator_id == current_operator_id:
            continue
        b.button(text=f"Оператор {operator_id}", callback_data=f"tq:trto:{request_id}:{operator_id}")
    b.button(text="Свободный оператор", callback_data=f"tq:trto:{request_id}:free")
    b.button(text="Отмена", callback_data=f"tq:open:{request_id}")
    b.adjust(1)
    return b.as_markup()


def ticket_transfer_reason_keyboard(request_id: str, to_operator: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    reasons = [
        ("Конец смены", "shift_end"),
        ("Перегрузка", "overload"),
        ("Язык клиента", "client_language"),
        ("Нужен старший", "senior_needed"),
        ("Отсутствие", "absence"),
    ]
    for title, key in reasons:
        b.button(text=title, callback_data=f"tq:trwhy:{request_id}:{to_operator}:{key}")
    b.button(text="Другая причина", callback_data=f"tq:trwhy:{request_id}:{to_operator}:other")
    b.button(text="Отмена", callback_data=f"tq:open:{request_id}")
    b.adjust(1)
    return b.as_markup()


def quick_comment_keyboard(request_id: str, templates: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for template in templates:
        b.button(text=template["title"], callback_data=f"tq:cquick:{request_id}:{template['key']}")
    b.button(text="Ввести комментарий", callback_data=f"tq:cadd:{request_id}")
    b.button(text="Отмена", callback_data=f"tq:open:{request_id}")
    b.adjust(1)
    return b.as_markup()
