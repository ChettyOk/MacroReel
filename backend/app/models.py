from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    picture_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    security_question: Mapped[str | None] = mapped_column(String(300), nullable=True)
    security_answer_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Recipe(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    ingredients: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: list[str]
    steps: Mapped[str] = mapped_column(Text, nullable=False)  # JSON: list[str]

    prep_time_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cook_time_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dietary_flags: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: list[str]
    nutrition: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: NutritionReport
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_platform: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_context_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DailyLogEntry(Base):
    """Meals logged per day, scoped to a user."""

    __tablename__ = "daily_log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    log_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    recipe_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    servings: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    nutrition: Mapped[str] = mapped_column(Text, nullable=False)  # JSON Nutrition per serving
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Profile(Base):
    """User profile and macro targets."""

    __tablename__ = "profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_profiles_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    height_cm: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)  # male/female/other
    activity_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    goal: Mapped[str | None] = mapped_column(String(20), nullable=True)  # lose/maintain/gain
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: list[str]
    dietary_prefs: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: list[str]
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
