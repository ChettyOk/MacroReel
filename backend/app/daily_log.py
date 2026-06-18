"""Server-side daily meal log, scoped per user."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyLogEntry, User
from app.schemas import DailyLogDay, DailyLogEntryCreate, DailyLogEntryRead, DailyLogWeekDay, Nutrition


def _today() -> str:
    return date.today().isoformat()


def _parse_nutrition(raw: str) -> Nutrition:
    try:
        return Nutrition.model_validate(json.loads(raw))
    except (ValueError, TypeError):
        return Nutrition()


def get_log_for_date(db: Session, user: User, log_date: str | None) -> DailyLogDay:
    d = log_date or _today()
    rows = db.scalars(
        select(DailyLogEntry)
        .where(DailyLogEntry.user_id == user.id, DailyLogEntry.log_date == d)
        .order_by(DailyLogEntry.logged_at.asc())
    ).all()
    entries = [
        DailyLogEntryRead(
            id=r.id,
            recipe_id=r.recipe_id,
            title=r.title,
            servings=r.servings,
            nutrition=_parse_nutrition(r.nutrition),
            logged_at=r.logged_at,
        )
        for r in rows
    ]
    return DailyLogDay(date=d, entries=entries, totals=_sum_entries(entries))


def add_entry(db: Session, user: User, body: DailyLogEntryCreate) -> DailyLogEntryRead:
    d = body.log_date or _today()
    row = DailyLogEntry(
        user_id=user.id,
        log_date=d,
        recipe_id=body.recipe_id,
        title=body.title.strip(),
        servings=body.servings,
        nutrition=body.nutrition.model_dump_json(),
        logged_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return DailyLogEntryRead(
        id=row.id,
        recipe_id=row.recipe_id,
        title=row.title,
        servings=row.servings,
        nutrition=body.nutrition,
        logged_at=row.logged_at,
    )


def delete_entry(db: Session, user: User, entry_id: int) -> None:
    row = db.get(DailyLogEntry, entry_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(status_code=404, detail="Log entry not found")
    db.delete(row)
    db.commit()


def _sum_entries(entries: list[DailyLogEntryRead]) -> Nutrition:
    out = Nutrition(calories=0, protein_g=0, carbs_g=0, fat_g=0, fiber_g=0)
    for e in entries:
        n = e.nutrition
        s = e.servings
        out.calories = (out.calories or 0) + (n.calories or 0) * s
        out.protein_g = (out.protein_g or 0) + (n.protein_g or 0) * s
        out.carbs_g = (out.carbs_g or 0) + (n.carbs_g or 0) * s
        out.fat_g = (out.fat_g or 0) + (n.fat_g or 0) * s
        out.fiber_g = (out.fiber_g or 0) + (n.fiber_g or 0) * s
    return Nutrition(
        calories=round(out.calories or 0) or None,
        protein_g=round((out.protein_g or 0) * 10) / 10 or None,
        carbs_g=round((out.carbs_g or 0) * 10) / 10 or None,
        fat_g=round((out.fat_g or 0) * 10) / 10 or None,
        fiber_g=round((out.fiber_g or 0) * 10) / 10 or None,
    )


def week_summary(db: Session, user: User, days: int = 7) -> list[DailyLogWeekDay]:
    today = date.today()
    out: list[DailyLogWeekDay] = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        day = get_log_for_date(db, user, d)
        out.append(
            DailyLogWeekDay(
                date=d,
                meal_count=len(day.entries),
                calories=day.totals.calories,
            )
        )
    return out
