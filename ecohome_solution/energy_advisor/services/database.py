from __future__ import annotations

import os
from datetime import datetime, timedelta

from loguru import logger
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# ── ORM base ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ───────────────────────────────────────────────────────────

class EnergyUsage(Base):
    """Hourly energy consumption record per device."""

    __tablename__ = "energy_usage"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    consumption_kwh = Column(Float, nullable=False)
    device_type = Column(String(50), nullable=True)
    device_name = Column(String(100), nullable=True)
    cost_usd = Column(Float, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EnergyUsage(ts={self.timestamp}, "
            f"kwh={self.consumption_kwh}, device={self.device_name})>"
        )


class SolarGeneration(Base):
    """Hourly solar generation record."""

    __tablename__ = "solar_generation"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    generation_kwh = Column(Float, nullable=False)
    weather_condition = Column(String(50), nullable=True)
    temperature_c = Column(Float, nullable=True)
    solar_irradiance = Column(Float, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<SolarGeneration(ts={self.timestamp}, "
            f"kwh={self.generation_kwh}, weather={self.weather_condition})>"
        )


# ── Database manager ─────────────────────────────────────────────────

class DatabaseManager:
    """
    Thin wrapper around SQLAlchemy providing session-safe CRUD helpers.

    Usage:
        db = DatabaseManager(db_path="data/energy_data.db")
        db.create_tables()
    """

    def __init__(self, db_path: str = "data/energy_data.db") -> None:
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True)
        self.db_path = db_path
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        logger.debug("DatabaseManager initialised (path={})", db_path)

    def create_tables(self) -> None:
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created at {}", self.db_path)

    def get_session(self) -> Session:
        return self.SessionLocal()

    # ── Write helpers ────────────────────────────────────────────────

    def add_usage_record(
        self,
        timestamp: datetime,
        consumption_kwh: float,
        device_type: str | None = None,
        device_name: str | None = None,
        cost_usd: float | None = None,
    ) -> EnergyUsage:
        session = self.get_session()
        try:
            record = EnergyUsage(
                timestamp=timestamp,
                consumption_kwh=consumption_kwh,
                device_type=device_type,
                device_name=device_name,
                cost_usd=cost_usd,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        finally:
            session.close()

    def add_generation_record(
        self,
        timestamp: datetime,
        generation_kwh: float,
        weather_condition: str | None = None,
        temperature_c: float | None = None,
        solar_irradiance: float | None = None,
    ) -> SolarGeneration:
        session = self.get_session()
        try:
            record = SolarGeneration(
                timestamp=timestamp,
                generation_kwh=generation_kwh,
                weather_condition=weather_condition,
                temperature_c=temperature_c,
                solar_irradiance=solar_irradiance,
            )
            session.add(record)
            session.commit()
            session.refresh(record)
            return record
        finally:
            session.close()

    # ── Read helpers ─────────────────────────────────────────────────

    def get_usage_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[EnergyUsage]:
        session = self.get_session()
        try:
            return (
                session.query(EnergyUsage)
                .filter(EnergyUsage.timestamp >= start_date, EnergyUsage.timestamp <= end_date)
                .order_by(EnergyUsage.timestamp)
                .all()
            )
        finally:
            session.close()

    def get_generation_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> list[SolarGeneration]:
        session = self.get_session()
        try:
            return (
                session.query(SolarGeneration)
                .filter(
                    SolarGeneration.timestamp >= start_date,
                    SolarGeneration.timestamp <= end_date,
                )
                .order_by(SolarGeneration.timestamp)
                .all()
            )
        finally:
            session.close()

    def get_recent_usage(self, hours: int = 24) -> list[EnergyUsage]:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        return self.get_usage_by_date_range(start_time, end_time)

    def get_recent_generation(self, hours: int = 24) -> list[SolarGeneration]:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        return self.get_generation_by_date_range(start_time, end_time)

    def count_usage_records(self) -> int:
        session = self.get_session()
        try:
            return session.query(EnergyUsage).count()
        finally:
            session.close()

    def count_generation_records(self) -> int:
        session = self.get_session()
        try:
            return session.query(SolarGeneration).count()
        finally:
            session.close()
