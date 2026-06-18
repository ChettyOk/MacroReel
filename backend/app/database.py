from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import DATA_DIR

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATA_DIR / 'recipes.db'}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_missing_columns(table: str, columns: dict[str, str], inspector) -> None:
    if table not in inspector.get_table_names():
        return
    existing_cols = {col["name"] for col in inspector.get_columns(table)}
    missing_cols = {name: ddl for name, ddl in columns.items() if name not in existing_cols}
    if not missing_cols:
        return
    with engine.begin() as conn:
        for name, ddl in missing_cols.items():
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


# Columns added after v0.1 — applied non-destructively to existing SQLite DBs via ADD COLUMN.
_RECIPE_COLUMN_DDL = {
    "user_id": "INTEGER",
    "prep_time_min": "INTEGER",
    "cook_time_min": "INTEGER",
    "servings": "INTEGER",
    "dietary_flags": "TEXT",
    "nutrition": "TEXT",
    "source_url": "TEXT",
    "source_platform": "VARCHAR(40)",
    "source_context_text": "TEXT",
    "thumbnail_url": "TEXT",
}


def ensure_schema() -> None:
    """Create tables, then add any missing columns without dropping existing data."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    _add_missing_columns("recipes", _RECIPE_COLUMN_DDL, inspector)
    _add_missing_columns("profiles", {"user_id": "INTEGER"}, inspector)
    _add_missing_columns("daily_log_entries", {"user_id": "INTEGER"}, inspector)
    _add_missing_columns(
        "users",
        {
            "security_question": "TEXT",
            "security_answer_hash": "VARCHAR(255)",
        },
        inspector,
    )
