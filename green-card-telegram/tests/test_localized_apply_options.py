import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _constant(module_path: str, name: str):
    tree = ast.parse((ROOT / module_path).read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {module_path}")


def test_language_keyboard_uses_human_readable_language_names():
    languages = _constant("app/bots/client_bot/keyboards/language.py", "LANGUAGES")

    assert ("ru", "Русская") in languages
    assert ("en", "English") in languages
    assert all(label != code.upper() for code, label in languages)


def test_apply_choice_buttons_use_localization_keys_and_stable_values():
    countries = _constant("app/bots/client_bot/keyboards/apply.py", "COUNTRIES")
    vehicle_types = _constant("app/bots/client_bot/keyboards/apply.py", "VEHICLE_TYPES")
    fuel_types = _constant("app/bots/client_bot/keyboards/apply.py", "FUEL_TYPES")
    power_units = _constant("app/bots/client_bot/keyboards/apply.py", "POWER_UNITS")

    assert ("belarus", "application.options.countries.belarus") in countries
    assert ("car", "application.options.vehicle_types.car") in vehicle_types
    assert ("petrol", "application.options.fuel_types.petrol") in fuel_types
    assert ("hp", "application.options.power_units.hp") in power_units
