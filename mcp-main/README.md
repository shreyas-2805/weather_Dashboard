# MCP Learning Console

An interactive lab project demonstrating a Model Context Protocol server and
client through a polished Gradio dashboard.

## Experiments included

### Experiment 1 — Personal Assistant Memory

Persistent notes are stored in `notes.db`, a local SQLite database managed by
SQLAlchemy and accessed only through MCP:

- `save_note(content, tags)` — create
- `search_notes(query)` and `list_notes()` — read
- `update_note(note_id, content, tags)` — update
- `delete_note(note_id)` — delete

### Experiment 2 — Data Dashboard Connector

`get_current_weather(location)` retrieves current structured weather data from
wttr.in. The UI displays temperature, condition, humidity, wind, and the raw
MCP response.

The project also includes `suggest_study(subject)` for generating a short study
path and interactive completion checklist.

## SQLite database

`database.py` defines the SQLAlchemy `Note` model and creates
`C:\Users\licha\Downloads\mcp\notes.db` automatically. SQLite is configured
with `check_same_thread=False` and one session per MCP call so simultaneous
Gradio requests are safe.

The first startup migrates valid records from the original `notes.json`,
preserving IDs, content, tags, and timestamps. After a successful import the
source is renamed to `notes.json.backup`; it is no longer read by the server.
The backup can be opened for inspection, but `notes.db` is the only active
memory store.

To inspect the database, use any SQLite browser or run:

```bat
python -c "from sqlalchemy import create_engine, text; e=create_engine('sqlite:///notes.db'); print(e.connect().execute(text('select id, content, tags from notes')).all())"
```

## Install and run

Open Anaconda Prompt:

```bat
conda activate Gen_ai
cd /d C:\Users\licha\Downloads\mcp
python -m pip install -r requirements.txt
python app.py
```

The dashboard opens at <http://127.0.0.1:7860>. You can also double-click
`run_gen_ai.bat`.

The command-line client is still available:

```bat
python client.py
python client.py --demo
```

## LLM routing

The client uses a Groq/OpenAI-compatible chat endpoint when the following
variables exist in the local `.env` file:

```text
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_MODEL=openai/gpt-oss-20b
```

The real `.env` file is ignored by Git and must never be uploaded. Use
`.env.example` as the safe configuration template. If the API is unavailable,
the client automatically falls back to its deterministic local router.

## Dashboard tabs

- **AI Assistant:** natural-language chat plus visible MCP tool selection,
  arguments, reason, router provider, and activity log
- **Memory Notes:** complete note CRUD interface with search and status feedback
- **Weather Dashboard:** live weather cards and structured tool output
- **Study Planner:** subject suggestions and progress checklist

## Submission screenshots

Store screenshots in the `screenshots` folder. Recommended captures:

1. AI Assistant showing a successful Groq LLM decision and MCP tool trace.
2. Memory Notes showing saved notes and CRUD controls.
3. Weather Dashboard showing live weather cards.
4. Study Planner showing a generated learning path and checked progress.

Do not include the `.env` file or API key in screenshots or GitHub commits.

## Project files

- `app.py` — interactive Gradio dashboard
- `server.py` — MCP server and tools
- `client.py` — reusable MCP client, LLM router, and CLI
- `database.py` — SQLite engine, SQLAlchemy model, and one-time migration
- `notes.db` — persistent local memory (generated and ignored by Git)
- `notes.json.backup` — preserved pre-migration JSON backup, if imported
- `requirements.txt` — pinned dependencies
- `run_gen_ai.bat` — Windows UI launcher
- `run_cli.bat` — Windows terminal-client launcher

References: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk),
[Groq OpenAI compatibility](https://console.groq.com/docs/openai), and
[Gradio documentation](https://www.gradio.app/docs).
