"""SQLAlchemy models for SkyWatch Pilot."""

from __future__ import annotations

from sqlalchemy import Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    pilot_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), default="Pilot")
    home_base: Mapped[str] = mapped_column(String(255), default="")
    license_id: Mapped[str] = mapped_column(String(128), default="")
    last_login: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Drone(Base):
    __tablename__ = "drones"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    pilot_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    altitude_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_seen: Mapped[str | None] = mapped_column(String(64), nullable=True)
    history_json: Mapped[str] = mapped_column(Text, default="[]")


class AckActive(Base):
    __tablename__ = "ack_active"
    __table_args__ = (UniqueConstraint("pilot_id", "alert_id", name="uq_ack_active"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pilot_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    alert_id: Mapped[str] = mapped_column(String(128), nullable=False)


class AckHistory(Base):
    __tablename__ = "ack_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pilot_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    alert_id: Mapped[str] = mapped_column(String(128), nullable=False)
    drone_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    drone_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    battery_percent: Mapped[int | None] = mapped_column(Integer, nullable=True)
    acknowledged_at: Mapped[str] = mapped_column(String(64), nullable=False)
