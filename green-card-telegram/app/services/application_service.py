from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import and_, or_, select

from app.db.models import Application, Policyholder, UploadedDocument, Vehicle
from app.db.session import SessionLocal
from app.schemas.application import ApplicationCreate


class ApplicationService:
    def create_local(self, payload: ApplicationCreate, tg_user_id: int | None, tg_username: str | None, tg_lang: str | None) -> tuple[Application, bool]:
        with SessionLocal() as db:
            duplicate = self._find_duplicate(db, payload, tg_user_id)
            if duplicate:
                return duplicate, True

            app = Application(
                request_id=str(uuid4()),
                telegram_user_id=tg_user_id,
                telegram_username=tg_username,
                telegram_language_code=tg_lang,
                status="new",
            )
            db.add(app)
            db.flush()
            db.add(Policyholder(
                application_id=app.id,
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone=payload.phone,
                email=payload.email,
                preferred_language=payload.preferred_language,
                policyholder_type=payload.policyholder_type.value,
                birth_date=str(payload.birth_date),
                registration_address=payload.registration_address,
                passport_series_number=payload.passport_series_number,
            ))
            for v in payload.vehicles:
                vehicle = Vehicle(
                    application_id=app.id,
                    vehicle_country_registration=v.vehicle_country_registration,
                    vehicle_type=v.vehicle_type,
                    insurance_start_date=str(v.insurance_start_date),
                    insurance_period_days=v.insurance_period_days,
                    license_plate=v.license_plate,
                    vin=v.vin,
                    brand_model=v.brand_model,
                    manufacture_year=v.manufacture_year,
                    engine_type=v.engine_type,
                    engine_capacity_cc=v.engine_capacity_cc,
                    engine_power=v.engine_power,
                    power_unit=v.power_unit,
                    comment="",
                )
                db.add(vehicle)
                db.flush()
                if v.vehicle_docs:
                    db.add(UploadedDocument(request_id=app.request_id, vehicle_id=vehicle.id, original_filename=str(v.vehicle_docs), mime_type="meta", size_bytes=0, storage_path="todo", bitrix_file_id=None))
            db.commit()
            db.refresh(app)
            return app, False

    def _find_duplicate(self, db, payload: ApplicationCreate, tg_user_id: int | None):
        dup_contact = db.scalar(
            select(Application)
            .join(Policyholder, Policyholder.application_id == Application.id)
            .where(or_(Policyholder.phone == payload.phone, Policyholder.email == payload.email, Application.telegram_user_id == tg_user_id))
            .order_by(Application.created_at.desc())
        )
        if not dup_contact:
            return None
        window_from = datetime.utcnow() - timedelta(hours=24)
        first_v = payload.vehicles[0]
        dup_app = db.scalar(
            select(Application)
            .join(Policyholder, Policyholder.application_id == Application.id)
            .join(Vehicle, Vehicle.application_id == Application.id)
            .where(
                and_(
                    Vehicle.vin == first_v.vin,
                    Vehicle.license_plate == first_v.license_plate,
                    Vehicle.insurance_start_date == str(first_v.insurance_start_date),
                    Policyholder.phone == payload.phone,
                    Application.created_at >= window_from,
                )
            )
            .order_by(Application.created_at.desc())
        )
        return dup_app

    def mark_bitrix_pending(self, request_id: str):
        with SessionLocal() as db:
            app = db.scalar(select(Application).where(Application.request_id == request_id))
            if app:
                app.status = "bitrix_pending"
                db.commit()

    def mark_bitrix_created(self, request_id: str, contact_id: int | None, company_id: int | None, deal_ids: list[int]):
        with SessionLocal() as db:
            app = db.scalar(select(Application).where(Application.request_id == request_id))
            if not app:
                return
            app.status = "bitrix_created"
            app.bitrix_contact_id = contact_id
            app.bitrix_company_id = company_id
            vehicles = list(db.scalars(select(Vehicle).where(Vehicle.application_id == app.id).order_by(Vehicle.id.asc())))
            for idx, deal_id in enumerate(deal_ids):
                if idx < len(vehicles):
                    vehicles[idx].bitrix_deal_id = deal_id
            db.commit()
