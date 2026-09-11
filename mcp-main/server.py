"""Simple MCP server for the two lab experiments.

Notes are persisted in SQLite through SQLAlchemy. The server communicates over
stdio, so normal output is returned by MCP tools rather than printed to stdout.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from mcp.server import MCPServer
from sqlalchemy import String, cast, or_, select
from sqlalchemy.exc import SQLAlchemyError

from database import Note, SessionLocal, initialize_database, note_to_dict, notes_query


mcp = MCPServer(
    "Personal Assistant and Data Dashboard",
    instructions="Use note tools for persistent memory, get_current_weather for live weather, and suggest_study for study planning.",
)
MIGRATION_RESULT = initialize_database()


def _normalise_tags(tags: str | list[str] | None) -> list[str]:
    if isinstance(tags, list):
        values = tags
    else:
        values = (tags or "").split(",")
    return sorted({str(tag).strip().lower() for tag in values if str(tag).strip()})


def _error(message: str) -> str:
    return json.dumps({"error": message})


@mcp.tool()
def save_note(content: str, tags: str = "") -> str:
    """Create a note and persist it in the SQLite database."""
    content = content.strip()
    if not content:
        return _error("content cannot be empty")
    note = Note(
        id=uuid.uuid4().hex[:8],
        content=content,
        tags=_normalise_tags(tags),
        created_at=datetime.now(timezone.utc),
    )
    session = SessionLocal()
    try:
        with session:
            session.add(note)
            session.commit()
            session.refresh(note)
            payload = note_to_dict(note)
        return json.dumps({"message": "Note saved", "note": payload}, indent=2)
    except SQLAlchemyError as exc:
        session.rollback()
        return _error(f"Could not save note: {exc}")


@mcp.tool()
def search_notes(query: str) -> str:
    """Find saved notes whose content or tags contain the query."""
    query = query.strip().lower()
    if not query:
        return _error("query cannot be empty")
    pattern = f"%{query}%"
    try:
        with SessionLocal() as session:
            matches = session.scalars(
                select(Note)
                .where(or_(Note.content.ilike(pattern), cast(Note.tags, String).ilike(pattern)))
                .order_by(Note.created_at.desc())
            ).all()
        return json.dumps(
            {"query": query, "count": len(matches), "matches": [note_to_dict(note) for note in matches]},
            indent=2,
        )
    except SQLAlchemyError as exc:
        return _error(f"Could not search notes: {exc}")


@mcp.tool()
def list_notes() -> str:
    """Read all notes from persistent SQLite memory."""
    try:
        with SessionLocal() as session:
            notes = session.scalars(notes_query()).all()
        return json.dumps({"count": len(notes), "notes": [note_to_dict(note) for note in notes]}, indent=2)
    except SQLAlchemyError as exc:
        return _error(f"Could not list notes: {exc}")


@mcp.tool()
def update_note(note_id: str, content: str, tags: str = "") -> str:
    """Update an existing note by its id."""
    session = SessionLocal()
    try:
        with session:
            note = session.get(Note, note_id.strip())
            if note is None:
                return _error(f"No note found with id {note_id}")
            if content.strip():
                note.content = content.strip()
            note.tags = _normalise_tags(tags)
            note.updated_at = datetime.now(timezone.utc)
            session.commit()
            session.refresh(note)
            payload = note_to_dict(note)
        return json.dumps({"message": "Note updated", "note": payload}, indent=2)
    except SQLAlchemyError as exc:
        session.rollback()
        return _error(f"Could not update note: {exc}")


@mcp.tool()
def delete_note(note_id: str) -> str:
    """Delete an existing note by its id."""
    session = SessionLocal()
    try:
        with session:
            note = session.get(Note, note_id.strip())
            if note is None:
                return _error(f"No note found with id {note_id}")
            session.delete(note)
            session.commit()
        return json.dumps({"message": "Note deleted", "id": note_id.strip()})
    except SQLAlchemyError as exc:
        session.rollback()
        return _error(f"Could not delete note: {exc}")


@mcp.tool()
def get_current_weather(location: str) -> str:
    """Fetch current weather from wttr.in and return a compact JSON record."""
    location = location.strip()
    if not location:
        return _error("location cannot be empty")
    url = f"https://wttr.in/{quote(location)}?format=j1"
    try:
        request = Request(url, headers={"User-Agent": "mcp-study-lab/1.0"})
        with urlopen(request, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
        current = data["current_condition"][0]
        area = data.get("nearest_area", [{}])[0]
        resolved = area.get("areaName", [{"value": location}])[0].get("value", location)
        result = {
            "location": location,
            "resolved_area": resolved,
            "temperature_c": current.get("temp_C"),
            "feels_like_c": current.get("FeelsLikeC"),
            "condition": current.get("weatherDesc", [{"value": "Unknown"}])[0].get("value"),
            "humidity_percent": current.get("humidity"),
            "wind_kph": current.get("windspeedKmph"),
            "observed_at": current.get("observation_time"),
        }
        return json.dumps(result, indent=2)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError) as exc:
        return _error(f"Weather lookup failed: {exc}")


SUBJECTS = {
    "python": ["Variables and data types", "Loops and functions", "Lists and dictionaries"],
    "math": ["Algebra", "Probability", "Basic calculus"],
    "ai": ["Python basics", "Machine learning fundamentals", "Neural networks"],
    "dbms": ["SQL queries", "Database normalization", "Joins and transactions"],
    "networks": ["OSI and TCP/IP models", "IP addressing", "TCP and UDP"],
}


@mcp.tool()
def suggest_study(subject: str = "") -> str:
    """Suggest a few beginner-friendly subjects or topics to study."""
    subject = subject.strip().lower()
    if not subject:
        return json.dumps({"subjects": list(SUBJECTS)}, indent=2)
    if subject not in SUBJECTS:
        return _error(f"Unknown subject; try one of: {', '.join(SUBJECTS)}")
    return json.dumps(
        {"subject": subject, "topics": SUBJECTS[subject], "tip": "Start with topic 1 and practise a small example."},
        indent=2,
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
