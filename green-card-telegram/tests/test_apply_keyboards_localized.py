from types import ModuleType, SimpleNamespace
import sys


def _install_aiogram_keyboard_stub():
    if "aiogram.types" in sys.modules and "aiogram.utils.keyboard" in sys.modules:
        return

    aiogram = ModuleType("aiogram")
    types = ModuleType("aiogram.types")
    utils = ModuleType("aiogram.utils")
    keyboard = ModuleType("aiogram.utils.keyboard")

    class InlineKeyboardBuilder:
        def __init__(self):
            self._buttons = []

        def button(self, text, callback_data):
            self._buttons.append(SimpleNamespace(text=text, callback_data=callback_data))

        def adjust(self, *sizes):
            self._sizes = sizes

        def as_markup(self):
            rows = []
            index = 0
            sizes = getattr(self, "_sizes", ()) or (len(self._buttons),)
            for size in sizes:
                if index >= len(self._buttons):
                    break
                rows.append(self._buttons[index : index + size])
                index += size
            if index < len(self._buttons):
                rows.append(self._buttons[index:])
            return SimpleNamespace(inline_keyboard=rows)

    types.InlineKeyboardMarkup = object
    keyboard.InlineKeyboardBuilder = InlineKeyboardBuilder
    sys.modules.setdefault("aiogram", aiogram)
    sys.modules.setdefault("aiogram.types", types)
    sys.modules.setdefault("aiogram.utils", utils)
    sys.modules.setdefault("aiogram.utils.keyboard", keyboard)


_install_aiogram_keyboard_stub()

_installed_i18n_stub = False
try:
    import yaml  # noqa: F401
except ModuleNotFoundError:
    i18n_service = ModuleType("app.services.i18n_service")

    class I18nService:
        pass

    i18n_service.I18nService = I18nService
    sys.modules.setdefault("app.services.i18n_service", i18n_service)
    _installed_i18n_stub = True

from app.bots.client_bot.keyboards.apply import (  # noqa: E402
    countries_keyboard,
    fuel_types_keyboard,
    periods_keyboard,
    power_units_keyboard,
    vehicle_types_keyboard,
)
from app.bots.client_bot.keyboards.calculator import (  # noqa: E402
    apply_cta_keyboard as calculator_apply_cta_keyboard,
)

if _installed_i18n_stub:
    sys.modules.pop("app.services.i18n_service", None)
    services_module = sys.modules.get("app.services")
    if services_module is not None and hasattr(services_module, "i18n_service"):
        delattr(services_module, "i18n_service")


class FakeI18n:
    texts = {
        "application.options.period_days": "{days} օր",
        "application.options.countries.armenia": "Հայաստան",
        "application.options.countries.russia": "Ռուսաստան",
        "application.options.vehicle_types.car": "Թեթև ավտոմեքենա",
        "application.options.fuel_types.petrol": "Բենզին",
        "application.options.power_units.hp": "Ձիաուժ",
        "calculator.apply_cta": "📝 Ուղարկել հայտ",
    }

    def get_text(self, lang, key, fallback_lang="en"):
        return self.texts.get(key, key)


I18N = FakeI18n()


def _button_texts(markup):
    return [button.text for row in markup.inline_keyboard for button in row]


def _callback_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_application_option_keyboards_are_localized_for_armenian():
    country_texts = _button_texts(countries_keyboard(I18N, "hy"))
    vehicle_texts = _button_texts(vehicle_types_keyboard(I18N, "hy"))
    fuel_texts = _button_texts(fuel_types_keyboard(I18N, "hy"))
    power_texts = _button_texts(power_units_keyboard(I18N, "hy"))
    period_texts = _button_texts(periods_keyboard(I18N, "hy"))

    assert "Հայաստան" in country_texts
    assert "Ռուսաստան" in country_texts
    assert "Легковой" not in vehicle_texts
    assert "Թեթև ավտոմեքենա" in vehicle_texts
    assert "Բենզին" in fuel_texts
    assert "Ձիաուժ" in power_texts
    assert "30 օր" in period_texts
    assert "30 дней" not in period_texts


def test_application_option_callbacks_keep_existing_canonical_values():
    assert "apply:country:Армения" in _callback_data(countries_keyboard(I18N, "hy"))
    assert "apply:vtype:Легковой" in _callback_data(vehicle_types_keyboard(I18N, "hy"))
    assert "apply:fuel:Бензин" in _callback_data(fuel_types_keyboard(I18N, "hy"))
    assert "apply:power:Лошадиные силы" in _callback_data(power_units_keyboard(I18N, "hy"))
    assert "apply:period:30" in _callback_data(periods_keyboard(I18N, "hy"))


def test_calculator_apply_cta_is_inline_button():
    markup = calculator_apply_cta_keyboard(I18N, "hy")

    assert _button_texts(markup) == ["📝 Ուղարկել հայտ"]
    assert _callback_data(markup) == ["calc:apply"]
