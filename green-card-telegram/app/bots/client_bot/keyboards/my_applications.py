from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services.i18n_service import I18nService


def application_actions_keyboard(
    i18n: I18nService, lang: str, deal_id: int, actions: dict
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if actions.get("open"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.open_button"),
            callback_data=f"myapp:open:{deal_id}",
        )
    if actions.get("repeat"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.repeat_button"),
            callback_data=f"myapp:repeat:{deal_id}",
        )
    if actions.get("upload_payment"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.payment_button"),
            callback_data=f"myapp:payment:{deal_id}",
        )
    if actions.get("policy_status"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.policy_status_button"),
            callback_data=f"myapp:policy_status:{deal_id}",
        )
    if actions.get("get_policy"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.policy_button"),
            callback_data=f"myapp:policy:{deal_id}",
        )
    if actions.get("contact_operator"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.operator_button"),
            callback_data=f"myapp:operator:{deal_id}",
        )
    builder.adjust(1)
    return builder.as_markup()


def contact_operator_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text(lang, "my_applications.operator_button"),
        callback_data="myapp:operator:none",
    )
    return builder.as_markup()


def repeat_periods_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for days in (30, 60, 90, 180, 365):
        builder.button(
            text=i18n.get_text(lang, "application.options.period_days").format(days=days),
            callback_data=f"repeat:period:{days}",
        )
    builder.adjust(3, 2)
    return builder.as_markup()


def repeat_docs_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text(lang, "repeat_application.docs_reuse_button"),
        callback_data="repeat:docs:reuse",
    )
    builder.button(
        text=i18n.get_text(lang, "repeat_application.docs_upload_new_button"),
        callback_data="repeat:docs:upload_new",
    )
    builder.adjust(1)
    return builder.as_markup()


def repeat_confirm_keyboard(i18n: I18nService, lang: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text=i18n.get_text(lang, "repeat_application.confirm_button"),
        callback_data="repeat:confirm",
    )
    builder.button(
        text=i18n.get_text(lang, "repeat_application.change_button"),
        callback_data="repeat:change",
    )
    builder.button(
        text=i18n.get_text(lang, "repeat_application.cancel_button"),
        callback_data="repeat:cancel",
    )
    builder.adjust(1)
    return builder.as_markup()

def policy_status_keyboard(
    i18n: I18nService, lang: str, deal_id: int, actions: dict
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if actions.get("get_policy"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.policy_button"),
            callback_data=f"myapp:policy:{deal_id}",
        )
    if actions.get("upload_payment"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.payment_button"),
            callback_data=f"myapp:payment:{deal_id}",
        )
    if actions.get("check_later"):
        builder.button(
            text=i18n.get_text(lang, "policy_status.check_later_button"),
            callback_data=f"myapp:policy_status:{deal_id}",
        )
    if actions.get("contact_operator"):
        builder.button(
            text=i18n.get_text(lang, "my_applications.operator_button"),
            callback_data=f"myapp:operator:{deal_id}",
        )
    if actions.get("back_to_applications"):
        builder.button(
            text=i18n.get_text(lang, "policy_status.back_to_applications_button"),
            callback_data="myapp:list",
        )
    builder.adjust(1)
    return builder.as_markup()
