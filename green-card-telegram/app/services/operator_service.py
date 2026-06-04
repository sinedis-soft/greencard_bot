from __future__ import annotations

import json
import os
from datetime import datetime

from sqlalchemy import select

from app.db.models import Operator
from app.db.session import SessionLocal

VALID_OPERATOR_ROLES = {"operator", "senior_operator", "admin"}


def _operator_to_dict(operator: Operator) -> dict:
    return {
        "id": operator.id,
        "telegram_user_id": operator.telegram_user_id,
        "name": operator.name,
        "role": operator.role,
        "languages": json.loads(operator.languages_json or "[]"),
        "max_active_tickets": operator.max_active_tickets,
        "is_active": operator.is_active,
        "created_at": operator.created_at.isoformat() if operator.created_at else None,
        "updated_at": operator.updated_at.isoformat() if operator.updated_at else None,
    }


class OperatorService:
    def list_operators(self, include_inactive: bool = True) -> list[dict]:
        with SessionLocal() as db:
            stmt = select(Operator).order_by(Operator.is_active.desc(), Operator.name.asc())
            if not include_inactive:
                stmt = stmt.where(Operator.is_active == True)
            return [_operator_to_dict(item) for item in db.scalars(stmt)]

    def get_by_telegram_id(self, telegram_user_id: int) -> Operator | None:
        with SessionLocal() as db:
            operator = db.scalar(select(Operator).where(Operator.telegram_user_id == telegram_user_id))
            if operator:
                db.expunge(operator)
            return operator

    def is_active_operator(self, telegram_user_id: int) -> bool:
        try:
            operator = self.get_by_telegram_id(telegram_user_id)
        except Exception:
            operator = None
        if operator:
            return bool(operator.is_active)
        return telegram_user_id in self.env_operator_ids()

    def active_operator_ids(self) -> set[int]:
        try:
            with SessionLocal() as db:
                ids = set(db.scalars(select(Operator.telegram_user_id).where(Operator.is_active == True)))
        except Exception:
            ids = set()
        return ids or self.env_operator_ids()

    def privileged_operator_ids(self) -> set[int]:
        try:
            with SessionLocal() as db:
                ids = set(
                    db.scalars(
                        select(Operator.telegram_user_id).where(
                            Operator.is_active == True,
                            Operator.role.in_(("senior_operator", "admin")),
                        )
                    )
                )
        except Exception:
            ids = set()
        env_ids = self._env_ids("SENIOR_OPERATOR_IDS") | self._env_ids("ADMIN_OPERATOR_IDS")
        return ids | env_ids

    def create_operator(self, data: dict) -> dict:
        role = data.get("role") or "operator"
        if role not in VALID_OPERATOR_ROLES:
            raise ValueError("invalid_role")
        with SessionLocal() as db:
            operator = Operator(
                telegram_user_id=int(data["telegram_user_id"]),
                name=str(data["name"]),
                role=role,
                languages_json=json.dumps(data.get("languages") or []),
                max_active_tickets=int(data.get("max_active_tickets") or 10),
                is_active=bool(data.get("is_active", True)),
            )
            db.add(operator)
            db.commit()
            db.refresh(operator)
            return _operator_to_dict(operator)

    def update_operator(self, operator_id: int, data: dict) -> dict | None:
        with SessionLocal() as db:
            operator = db.get(Operator, operator_id)
            if not operator:
                return None
            if "telegram_user_id" in data:
                operator.telegram_user_id = int(data["telegram_user_id"])
            if "name" in data:
                operator.name = str(data["name"])
            if "role" in data:
                role = str(data["role"])
                if role not in VALID_OPERATOR_ROLES:
                    raise ValueError("invalid_role")
                operator.role = role
            if "languages" in data:
                operator.languages_json = json.dumps(data.get("languages") or [])
            if "max_active_tickets" in data:
                operator.max_active_tickets = int(data["max_active_tickets"])
            if "is_active" in data:
                operator.is_active = bool(data["is_active"])
            operator.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(operator)
            return _operator_to_dict(operator)

    def set_active(self, operator_id: int, is_active: bool) -> dict | None:
        return self.update_operator(operator_id, {"is_active": is_active})

    @staticmethod
    def env_operator_ids() -> set[int]:
        return OperatorService._env_ids("OPERATOR_IDS")

    @staticmethod
    def _env_ids(name: str) -> set[int]:
        return {int(x.strip()) for x in os.getenv(name, "").split(",") if x.strip()}
