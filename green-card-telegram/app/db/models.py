from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_language_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    source_channel: Mapped[str] = mapped_column(String(32), default="telegram_miniapp")
    status: Mapped[str] = mapped_column(String(32), default="new", index=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    bitrix_contact_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bitrix_company_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    policyholder: Mapped["Policyholder"] = relationship(back_populates="application", uselist=False)
    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="application")


class Policyholder(Base):
    __tablename__ = "policyholders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    first_name: Mapped[str] = mapped_column(String(128))
    last_name: Mapped[str] = mapped_column(String(128))
    phone: Mapped[str] = mapped_column(String(64), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    preferred_language: Mapped[str] = mapped_column(String(16))
    policyholder_type: Mapped[str] = mapped_column(String(32))
    birth_date: Mapped[str] = mapped_column(String(32))
    registration_address: Mapped[str] = mapped_column(Text)
    passport_series_number: Mapped[str] = mapped_column(String(64))
    application: Mapped[Application] = relationship(back_populates="policyholder")


class Vehicle(Base):
    __tablename__ = "vehicles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), index=True)
    vehicle_country_registration: Mapped[str] = mapped_column(String(16))
    vehicle_type: Mapped[str] = mapped_column(String(64))
    insurance_start_date: Mapped[str] = mapped_column(String(32), index=True)
    insurance_period_days: Mapped[int] = mapped_column(Integer)
    license_plate: Mapped[str] = mapped_column(String(64), index=True)
    vin: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    brand_model: Mapped[str] = mapped_column(String(255))
    manufacture_year: Mapped[int] = mapped_column(Integer)
    engine_type: Mapped[str] = mapped_column(String(32))
    engine_capacity_cc: Mapped[int | None] = mapped_column(Integer, nullable=True)
    engine_power: Mapped[float | None] = mapped_column(Float, nullable=True)
    power_unit: Mapped[str] = mapped_column(String(8))
    comment: Mapped[str] = mapped_column(Text, default="")
    bitrix_deal_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    application: Mapped[Application] = relationship(back_populates="vehicles")


class OperatorTicket(Base):
    __tablename__ = "operator_tickets"
    request_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")
    operator_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_response_deadline: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sla_breach: Mapped[bool] = mapped_column(default=False)
    last_client_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_operator_message_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OperatorActionLog(Base):
    __tablename__ = "operator_action_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    operator_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(128))
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_path: Mapped[str] = mapped_column(String(512))
    bitrix_file_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="new")


class BitrixSyncJob(Base):
    __tablename__ = "bitrix_sync_jobs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    job_type: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="bitrix_pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String(128), index=True)
    event_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
