def mask_plate(value: str | None) -> str | None:
    if not value:
        return None

    plate = str(value).replace(" ", "").replace("-", "").upper()
    if len(plate) <= 3:
        return "***"
    if len(plate) <= 5:
        return f"{plate[0]}***{plate[-1]}"
    return f"{plate[:2]}***{plate[-2:]}"
