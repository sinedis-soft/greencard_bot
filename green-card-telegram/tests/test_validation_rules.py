from app.validation import (
    is_latin_name,
    is_license_plate,
    is_passport_number,
    is_vin,
    normalize_license_plate,
    normalize_passport,
    normalize_vin,
)


def test_name_allows_latin_spaces_and_hyphens_only():
    assert is_latin_name("Anne Marie")
    assert is_latin_name("Smith-Jones")
    assert not is_latin_name("Иван")
    assert not is_latin_name("John2")


def test_passport_allows_only_latin_letters_and_digits():
    assert normalize_passport(" ab123 ") == "AB123"
    assert is_passport_number("AB123")
    assert not is_passport_number("AB 123")
    assert not is_passport_number("АБ123")


def test_license_plate_is_trimmed_uppercase_and_latin_alnum_3_to_8_chars():
    assert normalize_license_plate(" ab123 ") == "AB123"
    assert is_license_plate("AB123")
    assert not is_license_plate("AB")
    assert not is_license_plate("AB1234567")
    assert not is_license_plate("AB-123")
    assert not is_license_plate("АВ123")


def test_vin_is_trimmed_uppercase_17_chars_and_excludes_i_o_q():
    assert normalize_vin(" wvwzzz1jzxw000001 ") == "WVWZZZ1JZXW000001"
    assert is_vin("WVWZZZ1JZXW000001")
    assert not is_vin("WVWZZZ1JZXW00001")
    assert not is_vin("WVWZZZ1JZXW0000011")
    assert not is_vin("WVWZZZ1JZXW00000I")
    assert not is_vin("WVWZZZ1JZXW00000O")
    assert not is_vin("WVWZZZ1JZXW00000Q")
