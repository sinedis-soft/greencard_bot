import re

LATIN_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z -]*$")
PASSPORT_RE = re.compile(r"^[A-Za-z0-9]+$")
LICENSE_PLATE_RE = re.compile(r"^[A-Z0-9]{3,8}$")
VIN_RE = re.compile(r"^[A-HJ-NPR-Z0-9]{17}$")


def normalize_license_plate(value: object) -> str:
    return str(value or "").strip().upper()


def normalize_vin(value: object) -> str:
    return str(value or "").strip().upper()


def normalize_passport(value: object) -> str:
    return str(value or "").strip().upper()


def is_latin_name(value: str) -> bool:
    return bool(LATIN_NAME_RE.fullmatch(value.strip()))


def is_passport_number(value: str) -> bool:
    return bool(PASSPORT_RE.fullmatch(value))


def is_license_plate(value: str) -> bool:
    return bool(LICENSE_PLATE_RE.fullmatch(value))


def is_vin(value: str) -> bool:
    return bool(VIN_RE.fullmatch(value))
