"""SQLite persistence layer for the MCP note tools."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "notes.db"
LEGACY_JSON_PATH = BASE_DIR / "notes.json"
JSON_BACKUP_PATH = BASE_DIR / "notes.json.backup"

engine = create_engine(
    f"sqlite:///{DB_PATH.as_posix()}",
    connect_args={"check_same_thread": False, "timeout": 30},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


def _utc_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def note_to_dict(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "content": note.content,
        "tags": list(note.tags or []),
        "created_at": _utc_iso(note.created_at),
        **({"updated_at": _utc_iso(note.updated_at)} if note.updated_at else {}),
    }


def initialize_database() -> dict[str, int]:
    """Create tables and import the legacy JSON file once, if present."""
    Base.metadata.create_all(engine)
    imported = 0
    skipped = 0
    if not LEGACY_JSON_PATH.exists() or JSON_BACKUP_PATH.exists():
        return {"imported": imported, "skipped": skipped}

    try:
        raw = json.loads(LEGACY_JSON_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"imported": imported, "skipped": 1}
    if not isinstance(raw, list):
        return {"imported": imported, "skipped": 1}

    def parse_timestamp(value: object, fallback: datetime | None = None) -> datetime | None:
        if value in (None, ""):
            return fallback
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return fallback
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    with SessionLocal() as session:
        existing_count = session.scalar(select(func.count()).select_from(Note)) or 0
        if existing_count:
            return {"imported": imported, "skipped": skipped}
        seen_ids: set[str] = set()
        try:
            for item in raw:
                if not isinstance(item, dict):
                    skipped += 1
                    continue
                note_id = str(item.get("id", "")).strip()
                content = str(item.get("content", "")).strip()
                if not note_id or not content or note_id in seen_ids:
                    skipped += 1
                    continue
                seen_ids.add(note_id)
                created_at = parse_timestamp(item.get("created_at"), datetime.now(timezone.utc))
                updated_at = parse_timestamp(item.get("updated_at"))
                tags = item.get("tags", [])
                if not isinstance(tags, list):
                    tags = [str(tags)]
                session.add(
                    Note(
                        id=note_id,
                        content=content,
                        tags=sorted({str(tag).strip().lower() for tag in tags if str(tag).strip()}),
                        created_at=created_at,
                        updated_at=updated_at,
                    )
                )
                imported += 1
            session.commit()
        except Exception:
            session.rollback()
            raise

    if imported or not raw:
        try:
            LEGACY_JSON_PATH.replace(JSON_BACKUP_PATH)
        except OSError:
            pass
    return {"imported": imported, "skipped": skipped}


def notes_query():
    return select(Note).order_by(Note.created_at.desc())
