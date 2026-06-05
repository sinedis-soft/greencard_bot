from app.bots.client_bot.menu_actions import menu_action_for_text


class FakeI18n:
    dictionaries = {
        "en": {
            "main_menu.calculator": "🧮 Calculator",
            "main_menu.faq": "❓ FAQ",
            "main_menu.coverage": "🌍 Where does it work?",
            "main_menu.apply": "📝 Submit an application",
            "main_menu.operator": "👨‍💼 Contact an operator",
            "main_menu.latest_deal": "📄 My latest application",
            "main_menu.my_applications": "📄 My applications",
            "main_menu.payment_confirmation": "💳 Payment confirmation",
            "main_menu.language": "🌐 Language",
            "calculator.apply_cta": "📝 Submit an application",
        },
        "ka": {
            "main_menu.calculator": "🧮 კალკულატორი",
            "main_menu.faq": "❓ FAQ",
            "main_menu.coverage": "🌍 სად მოქმედებს?",
            "main_menu.apply": "📝 გაფორმება",
            "main_menu.operator": "👨‍💼 ოპერატორთან დაკავშირება",
            "main_menu.latest_deal": "📄 ჩემი ბოლო განაცხადი",
            "main_menu.my_applications": "📄 Мои заявки",
            "main_menu.payment_confirmation": "💳 გადახდის დადასტურება",
            "main_menu.language": "🌐 ენა",
            "calculator.apply_cta": "📝 განაცხადის გაფორმება",
        },
        "kk": {
            "main_menu.calculator": "🧮 Калькулятор",
            "main_menu.faq": "❓ FAQ",
            "main_menu.coverage": "🌍 Қай жерде жұмыс істейді?",
            "main_menu.apply": "📝 Өтінім беру",
            "main_menu.operator": "👨‍💼 Оператормен байланысу",
            "main_menu.latest_deal": "📄 Менің соңғы өтінімім",
            "main_menu.my_applications": "📄 Мои заявки",
            "main_menu.payment_confirmation": "💳 Төлемді растау",
            "main_menu.language": "🌐 Тіл",
            "calculator.apply_cta": "📝 Өтінім беру",
        },
        "pl": {
            "main_menu.calculator": "🧮 Kalkulator",
            "main_menu.faq": "❓ FAQ",
            "main_menu.coverage": "🌍 Gdzie działa?",
            "main_menu.apply": "📝 Złóż wniosek",
            "main_menu.operator": "👨‍💼 Skontaktuj się z operatorem",
            "main_menu.latest_deal": "📄 My latest application",
            "main_menu.my_applications": "📄 My applications",
            "main_menu.payment_confirmation": "💳 Payment confirmation",
            "main_menu.language": "🌐 Język",
            "calculator.apply_cta": "📝 Złóż wniosek",
        },
        "ru": {
            "main_menu.calculator": "🧮 Калькулятор",
            "main_menu.faq": "❓ FAQ",
            "main_menu.coverage": "🌍 Где работает?",
            "main_menu.apply": "📝 Оформить заявку",
            "main_menu.operator": "👨‍💼 Связаться с оператором",
            "main_menu.latest_deal": "📄 Моя последняя заявка",
            "main_menu.my_applications": "📄 Мои заявки",
            "main_menu.payment_confirmation": "💳 Подтверждение оплаты",
            "main_menu.language": "🌐 Язык",
            "calculator.apply_cta": "📝 Оформить заявку",
        },
    }

    def available_languages(self):
        return tuple(sorted(self.dictionaries))

    def get_text(self, lang, key, fallback_lang="en"):
        return self.dictionaries.get(lang, self.dictionaries[fallback_lang]).get(
            key, key
        )


def test_menu_actions_match_localized_buttons_for_all_languages():
    i18n = FakeI18n()

    expected_actions = {
        "main_menu.calculator": "calculator",
        "main_menu.faq": "faq",
        "main_menu.coverage": "coverage",
        "main_menu.apply": "apply",
        "main_menu.operator": "operator",
        "main_menu.latest_deal": "latest_deal",
        "main_menu.my_applications": "my_applications",
        "main_menu.payment_confirmation": "payment_confirmation",
        "main_menu.language": "language",
    }

    for lang in i18n.available_languages():
        for key, action in expected_actions.items():
            assert (
                menu_action_for_text(i18n, i18n.get_text(lang, key), lang, "ru")
                == action
            )


def test_calculator_apply_cta_starts_apply_flow_in_every_language():
    i18n = FakeI18n()

    for lang in i18n.available_languages():
        assert (
            menu_action_for_text(
                i18n, i18n.get_text(lang, "calculator.apply_cta"), lang, "ru"
            )
            == "apply"
        )


def test_command_aliases_still_work():
    i18n = FakeI18n()

    assert menu_action_for_text(i18n, "/coverage", "pl", "ru") == "coverage"
    assert menu_action_for_text(i18n, "/lang", "ka", "ru") == "language"
    assert menu_action_for_text(i18n, "/latest", "ru", "ru") == "latest_deal"
    assert menu_action_for_text(i18n, "/my", "ru", "ru") == "my_applications"
    assert (
        menu_action_for_text(i18n, "/payment", "ru", "ru")
        == "payment_confirmation"
    )


def test_europolis_belarusian_menu_buttons_match_after_telegram_emoji_variation():
    i18n = FakeI18n()
    i18n.dictionaries["be"] = {
        "main_menu.calculator": "🧮 Калькулятар",
        "main_menu.faq": "❓ FAQ",
        "main_menu.coverage": "🌍 Дзе дзейнічае?",
        "main_menu.apply": "📝 Аформіць",
        "main_menu.operator": "👨‍💼 Звязацца з аператарам",
        "main_menu.latest_deal": "📄 Мая апошняя заяўка",
        "main_menu.my_applications": "📄 Мои заявки",
        "main_menu.payment_confirmation": "💳 Пацвярджэнне аплаты",
        "main_menu.language": "🌐 Мова",
        "calculator.apply_cta": "📝 Аформіць заяўку",
    }

    assert menu_action_for_text(i18n, "🌐️ Мова", "be", "ru") == "language"
    assert (
        menu_action_for_text(i18n, "👨‍💼️ Звязацца з аператарам", "be", "ru")
        == "operator"
    )
    assert (
        menu_action_for_text(i18n, "📄 Мая апошняя заяўка", "be", "ru")
        == "latest_deal"
    )
    assert menu_action_for_text(i18n, "Мои заявки", "be", "ru") == "my_applications"


def test_europolis_belarusian_menu_aliases_work_without_dictionary_context():
    i18n = FakeI18n()

    assert menu_action_for_text(i18n, "🌍 Дзе дзейнічае?", "be", "ru") == "coverage"
    assert menu_action_for_text(i18n, "📝 Аформіць", "be", "ru") == "apply"
    assert (
        menu_action_for_text(i18n, "💳 Пацвярджэнне аплаты", "be", "ru")
        == "payment_confirmation"
    )
