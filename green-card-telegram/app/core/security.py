from fastapi import HTTPException


def ensure_consents(terms_accepted: bool, privacy_accepted: bool) -> None:
    if not terms_accepted:
        raise HTTPException(status_code=400, detail="Terms must be accepted")
    if not privacy_accepted:
        raise HTTPException(status_code=400, detail="Privacy policy must be accepted")
