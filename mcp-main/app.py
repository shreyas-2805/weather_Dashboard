"""Gradio dashboard for the MCP Personal Assistant lab.

Every UI operation calls ``server.py`` through an MCP stdio connection.  The
UI never reads or writes the SQLite database directly.
"""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import gradio as gr
from mcp import Client, StdioServerParameters

from client import (
    SERVER_PATH,
    choose_tool_with_mode,
    configured_router_name,
    pretty_answer,
    text_from_result,
)


APP_DIR = Path(__file__).resolve().parent
ACTIVITY_HEADERS = ["Time", "Area", "MCP tool", "Arguments", "Status"]
NOTE_HEADERS = ["ID", "Content", "Tags", "Created", "Updated"]

CSS = r"""
:root {
  --ink: #e8eefc;
  --muted: #91a4c9;
  --panel: rgba(12, 24, 48, .86);
  --panel-2: rgba(19, 36, 68, .78);
  --line: rgba(132, 167, 232, .18);
  --cyan: #48d7ff;
  --blue: #6b8cff;
  --green: #52e6a4;
}
body, .gradio-container {
  background:
    radial-gradient(circle at 8% 0%, rgba(66, 93, 194, .25), transparent 34%),
    radial-gradient(circle at 90% 12%, rgba(16, 190, 220, .13), transparent 30%),
    #07101f !important;
  color: var(--ink) !important;
}
.gradio-container { max-width: 1440px !important; margin: auto !important; padding: 26px 24px 48px !important; }
.hero {
  border: 1px solid var(--line); border-radius: 24px; padding: 28px 30px; margin-bottom: 18px;
  background: linear-gradient(125deg, rgba(18, 38, 79, .94), rgba(8, 25, 48, .94));
  box-shadow: 0 24px 80px rgba(0, 0, 0, .34); position: relative; overflow: hidden;
}
.hero:after { content: ''; position: absolute; width: 240px; height: 240px; border-radius: 50%; right: -70px; top: -105px; background: rgba(72, 215, 255, .1); }
.eyebrow { color: var(--cyan); text-transform: uppercase; letter-spacing: .15em; font-size: 12px; font-weight: 800; }
.hero h1 { font-size: clamp(30px, 4vw, 50px); margin: 5px 0 8px; color: #fff; line-height: 1.05; }
.hero p { color: #b8c7e5; max-width: 820px; font-size: 16px; margin: 0; }
.status-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }
.pill { border: 1px solid var(--line); background: rgba(9, 20, 41, .65); padding: 7px 12px; border-radius: 999px; color: #c9d6f0; font-size: 12px; }
.pill.live:before { content: ''; display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--green); margin-right: 7px; box-shadow: 0 0 12px var(--green); }
.section-copy { color: var(--muted); margin-top: -5px; }
.panel, .gradio-group, .gradio-box { border-color: var(--line) !important; }
.panel { background: var(--panel) !important; border: 1px solid var(--line) !important; border-radius: 18px !important; padding: 16px !important; }
.tool-trace { background: rgba(8, 19, 39, .78) !important; border-left: 3px solid var(--cyan) !important; padding: 12px 16px !important; border-radius: 12px !important; }
.tool-trace code { background: #172a4b !important; color: #75e5ff !important; border: 1px solid rgba(117,229,255,.18); padding: 2px 5px; border-radius: 5px; }
#assistant-chatbot .message, #assistant-chatbot .message * { color: #edf4ff !important; }
#assistant-chatbot .message { background: #142642 !important; border: 1px solid rgba(132,167,232,.2) !important; }
#assistant-chatbot .message.user { background: linear-gradient(110deg, #355dd0, #168caa) !important; }
#assistant-chatbot .message.bot { background: #142642 !important; }
.gradio-container table, .gradio-container thead, .gradio-container tbody { background: #0c1930 !important; }
.gradio-container th, .gradio-container td { background: #101f39 !important; color: #e7efff !important; border-color: rgba(132,167,232,.16) !important; }
.gradio-container th button, .gradio-container td button { color: #e7efff !important; }
#study-checklist label { background: #142642 !important; border-color: rgba(132,167,232,.22) !important; }
#study-checklist label span { color: #e7efff !important; }
button[role="tab"] { background: transparent !important; color: #c3d1ed !important; }
button[role="tab"][aria-selected="true"] { color: #53dfff !important; border-bottom-color: #53dfff !important; }
.metric-grid { display: grid; grid-template-columns: repeat(4, minmax(130px, 1fr)); gap: 12px; margin-top: 14px; }
.metric { border: 1px solid var(--line); border-radius: 16px; padding: 17px; background: linear-gradient(145deg, rgba(22, 43, 81, .9), rgba(10, 25, 48, .9)); }
.metric .label { color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: .09em; }
.metric .value { color: #fff; font-size: 25px; font-weight: 750; margin-top: 7px; }
.weather-head { display: flex; align-items: center; justify-content: space-between; gap: 15px; }
.weather-head h3 { margin: 0; color: white; font-size: 26px; }
.weather-condition { color: var(--cyan); font-weight: 700; }
.success-card, .error-card { border-radius: 14px; padding: 14px 16px; margin: 8px 0; }
.success-card { border: 1px solid rgba(82,230,164,.3); background: rgba(26,98,77,.22); color: #bdf9dd; }
.error-card { border: 1px solid rgba(255,113,133,.35); background: rgba(127,32,52,.22); color: #ffd1d8; }
.footer-note { color: #6f83aa; text-align: center; font-size: 12px; margin-top: 16px; }
button.primary { background: linear-gradient(110deg, #4d70ef, #20b7da) !important; border: 0 !important; }
.tab-nav button { font-weight: 700 !important; }
textarea, input { background: rgba(7, 18, 37, .72) !important; }
@media (max-width: 760px) {
  .gradio-container { padding: 12px !important; }
  .hero { padding: 22px 20px; }
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
}
"""


def _safe(value: Any) -> str:
    return html.escape(str(value if value is not None else "—"))


async def mcp_call(tool: str, arguments: dict[str, Any]) -> str:
    """Call one server tool using a fresh stdio MCP session."""
    server = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with Client(server) as mcp_client:
        result = await mcp_client.call_tool(tool, arguments)
        body = text_from_result(result)
        if result.is_error:
            raise RuntimeError(body or f"MCP tool {tool} failed")
        return body


def _json(raw: str) -> dict[str, Any]:
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("The MCP tool returned an unexpected response")
    return data


def _log(activity: list[list[str]] | None, area: str, tool: str, arguments: dict, status: str) -> list[list[str]]:
    rows = list(activity or [])
    compact = json.dumps(arguments, ensure_ascii=False, separators=(",", ":"))
    rows.insert(0, [datetime.now().strftime("%H:%M:%S"), area, tool, compact, status])
    return rows[:30]


def _status(message: str, ok: bool = True) -> str:
    css_class = "success-card" if ok else "error-card"
    icon = "✓" if ok else "!"
    return f'<div class="{css_class}"><strong>{icon}</strong>&nbsp; {_safe(message)}</div>'


def _short_time(value: str | None) -> str:
    if not value:
        return "—"
    return value.replace("T", " ").replace("+00:00", " UTC")[:23]


def _note_rows(notes: list[dict[str, Any]]) -> list[list[str]]:
    return [
        [
            str(note.get("id", "")),
            str(note.get("content", "")),
            ", ".join(note.get("tags", [])),
            _short_time(note.get("created_at")),
            _short_time(note.get("updated_at")),
        ]
        for note in notes
    ]


async def _fetch_notes() -> list[dict[str, Any]]:
    data = _json(await mcp_call("list_notes", {}))
    if "error" in data:
        raise RuntimeError(data["error"])
    return data.get("notes", [])


async def chat_submit(message: str, history: list[dict] | None, activity: list[list[str]] | None):
    history = list(history or [])
    if not message or not message.strip():
        gr.Warning("Type a message before sending.")
        return "", history, "### Tool decision\nWaiting for a request…", "**Router:** ready", activity or [], activity or []

    request = message.strip()
    history.append({"role": "user", "content": request})
    try:
        tool, arguments, explanation, mode = await choose_tool_with_mode(request)
        raw = await mcp_call(tool, arguments)
        data = _json(raw)
        if "error" in data:
            raise RuntimeError(data["error"])
        answer = pretty_answer(tool, raw)
        history.append({"role": "assistant", "content": answer})
        trace = (
            "### MCP tool decision\n"
            f"**Router:** `{mode}`  \n"
            f"**Selected tool:** `{tool}`  \n"
            f"**Arguments:** `{json.dumps(arguments, ensure_ascii=False)}`  \n"
            f"**Reason:** {explanation}"
        )
        rows = _log(activity, "Assistant", tool, arguments, "Success")
        return "", history, trace, f"**Router:** {mode} · **MCP:** connected", rows, rows
    except Exception as exc:
        history.append({"role": "assistant", "content": f"I could not complete that request: {exc}"})
        rows = _log(activity, "Assistant", "routing/tool call", {"message": request}, "Error")
        return "", history, f"### MCP tool decision\n**Error:** {_safe(exc)}", "**MCP:** error handled", rows, rows


def clear_chat():
    return [], "### MCP tool decision\nYour selected tool and arguments will appear here.", "**Router:** ready"


async def refresh_notes(activity: list[list[str]] | None):
    try:
        notes = await _fetch_notes()
        rows = _log(activity, "Memory", "list_notes", {}, "Success")
        choices = [note.get("id", "") for note in notes]
        return _note_rows(notes), gr.update(choices=choices, value=None), notes, _status(f"Loaded {len(notes)} saved note(s)."), rows, rows
    except Exception as exc:
        rows = _log(activity, "Memory", "list_notes", {}, "Error")
        return [], gr.update(choices=[], value=None), [], _status(str(exc), False), rows, rows


async def save_note_ui(content: str, tags: str, activity: list[list[str]] | None):
    if not content or not content.strip():
        gr.Warning("Note content cannot be empty.")
        return content, tags, gr.update(), gr.update(), gr.update(), _status("Enter some note content first.", False), activity or [], activity or []
    arguments = {"content": content.strip(), "tags": (tags or "").strip()}
    try:
        data = _json(await mcp_call("save_note", arguments))
        if "error" in data:
            raise RuntimeError(data["error"])
        notes = await _fetch_notes()
        rows = _log(activity, "Memory", "save_note", arguments, "Success")
        choices = [note.get("id", "") for note in notes]
        gr.Info("Note saved to persistent MCP memory.")
        return "", "", _note_rows(notes), gr.update(choices=choices, value=data["note"]["id"]), notes, _status("Note saved successfully."), rows, rows
    except Exception as exc:
        rows = _log(activity, "Memory", "save_note", arguments, "Error")
        return content, tags, gr.update(), gr.update(), gr.update(), _status(str(exc), False), rows, rows


async def search_notes_ui(query: str, activity: list[list[str]] | None):
    if not query or not query.strip():
        return gr.update(), gr.update(), gr.update(), _status("Enter a search term.", False), activity or [], activity or []
    arguments = {"query": query.strip()}
    try:
        data = _json(await mcp_call("search_notes", arguments))
        if "error" in data:
            raise RuntimeError(data["error"])
        matches = data.get("matches", [])
        rows = _log(activity, "Memory", "search_notes", arguments, "Success")
        choices = [note.get("id", "") for note in matches]
        return _note_rows(matches), gr.update(choices=choices, value=None), matches, _status(f"Found {len(matches)} matching note(s)."), rows, rows
    except Exception as exc:
        rows = _log(activity, "Memory", "search_notes", arguments, "Error")
        return [], gr.update(choices=[], value=None), [], _status(str(exc), False), rows, rows


def choose_note(note_id: str | None, notes: list[dict] | None):
    if not note_id:
        return "", ""
    note = next((item for item in (notes or []) if item.get("id") == note_id), None)
    if not note:
        return "", ""
    return note.get("content", ""), ", ".join(note.get("tags", []))


async def update_note_ui(note_id: str | None, content: str, tags: str, activity: list[list[str]] | None):
    if not note_id:
        return gr.update(), gr.update(), gr.update(), _status("Choose a note ID to update.", False), activity or [], activity or []
    if not content or not content.strip():
        return gr.update(), gr.update(), gr.update(), _status("Updated content cannot be empty.", False), activity or [], activity or []
    arguments = {"note_id": note_id, "content": content.strip(), "tags": (tags or "").strip()}
    try:
        data = _json(await mcp_call("update_note", arguments))
        if "error" in data:
            raise RuntimeError(data["error"])
        notes = await _fetch_notes()
        rows = _log(activity, "Memory", "update_note", arguments, "Success")
        gr.Info("Note updated.")
        return _note_rows(notes), gr.update(choices=[n.get("id", "") for n in notes], value=note_id), notes, _status("Note updated successfully."), rows, rows
    except Exception as exc:
        rows = _log(activity, "Memory", "update_note", arguments, "Error")
        return gr.update(), gr.update(), gr.update(), _status(str(exc), False), rows, rows


async def delete_note_ui(note_id: str | None, activity: list[list[str]] | None):
    if not note_id:
        return gr.update(), gr.update(), gr.update(), "", "", _status("Choose a note ID to delete.", False), activity or [], activity or []
    arguments = {"note_id": note_id}
    try:
        data = _json(await mcp_call("delete_note", arguments))
        if "error" in data:
            raise RuntimeError(data["error"])
        notes = await _fetch_notes()
        rows = _log(activity, "Memory", "delete_note", arguments, "Success")
        gr.Info("Note deleted.")
        return _note_rows(notes), gr.update(choices=[n.get("id", "") for n in notes], value=None), notes, "", "", _status("Note deleted successfully."), rows, rows
    except Exception as exc:
        rows = _log(activity, "Memory", "delete_note", arguments, "Error")
        return gr.update(), gr.update(), gr.update(), gr.update(), gr.update(), _status(str(exc), False), rows, rows


def weather_card(data: dict[str, Any]) -> str:
    return f"""
    <div class="panel">
      <div class="weather-head">
        <div><div class="eyebrow">Live conditions</div><h3>{_safe(data.get('location', ''))}</h3></div>
        <div class="weather-condition">{_safe(data.get('condition'))}</div>
      </div>
      <div class="metric-grid">
        <div class="metric"><div class="label">Temperature</div><div class="value">{_safe(data.get('temperature_c'))} °C</div></div>
        <div class="metric"><div class="label">Feels like</div><div class="value">{_safe(data.get('feels_like_c'))} °C</div></div>
        <div class="metric"><div class="label">Humidity</div><div class="value">{_safe(data.get('humidity_percent'))}%</div></div>
        <div class="metric"><div class="label">Wind</div><div class="value">{_safe(data.get('wind_kph'))} km/h</div></div>
      </div>
      <p class="section-copy">Resolved area: {_safe(data.get('resolved_area'))} · Observation: {_safe(data.get('observed_at'))}</p>
    </div>
    """


async def weather_ui(location: str, activity: list[list[str]] | None):
    if not location or not location.strip():
        gr.Warning("Enter a city or location.")
        return _status("Enter a location to fetch live weather.", False), {}, activity or [], activity or []
    arguments = {"location": location.strip()}
    try:
        data = _json(await mcp_call("get_current_weather", arguments))
        if "error" in data:
            raise RuntimeError(data["error"])
        rows = _log(activity, "Weather", "get_current_weather", arguments, "Success")
        return weather_card(data), data, rows, rows
    except Exception as exc:
        rows = _log(activity, "Weather", "get_current_weather", arguments, "Error")
        return _status(f"Weather service unavailable: {exc}", False), {"error": str(exc)}, rows, rows


async def study_ui(subject: str, activity: list[list[str]] | None):
    arguments = {"subject": (subject or "").strip().lower()}
    try:
        data = _json(await mcp_call("suggest_study", arguments))
        if "error" in data:
            raise RuntimeError(data["error"])
        topics = data.get("topics", [])
        title = data.get("subject", "Study plan").upper()
        markdown = f"### {title} learning path\n\n" + "\n".join(f"{i}. **{topic}**" for i, topic in enumerate(topics, 1))
        markdown += f"\n\n> {data.get('tip', '')}"
        rows = _log(activity, "Study", "suggest_study", arguments, "Success")
        return markdown, gr.update(choices=topics, value=[]), f"**Progress:** 0 / {len(topics)} topics", rows, rows
    except Exception as exc:
        rows = _log(activity, "Study", "suggest_study", arguments, "Error")
        return f"### Unable to build plan\n\n{exc}", gr.update(choices=[], value=[]), "**Progress:** unavailable", rows, rows


def update_progress(completed: list[str] | None, subject: str):
    total = 3
    count = len(completed or [])
    percent = round((count / total) * 100) if total else 0
    return f"**{(subject or 'Study').title()} progress:** {count} / {total} topics · {percent}% complete"


def build_app() -> gr.Blocks:
    router_name = configured_router_name()
    theme = gr.themes.Base(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.cyan,
        neutral_hue=gr.themes.colors.slate,
        font=["Inter", "Segoe UI", "sans-serif"],
        font_mono=["JetBrains Mono", "Consolas", "monospace"],
    ).set(
        body_background_fill="#07101f",
        body_text_color="#e8eefc",
        block_background_fill="#0d1a31",
        block_border_color="rgba(132,167,232,.18)",
        input_background_fill="#09162b",
    )

    with gr.Blocks(theme=theme, css=CSS, title="MCP Learning Console", fill_width=True) as demo:
        activity_state = gr.State([])
        notes_state = gr.State([])

        gr.HTML(
            f"""
            <div class="hero">
              <div class="eyebrow">Model Context Protocol · Lab 06</div>
              <h1>MCP Learning Console</h1>
              <p>A persistent AI memory, live data connector, and study planner — all powered by a Python MCP server.</p>
              <div class="status-row">
                <span class="pill live">MCP server ready</span>
                <span class="pill">Router: {_safe(router_name)}</span>
                <span class="pill">Storage: SQLite · SQLAlchemy</span>
                <span class="pill">Environment: Gen_ai</span>
              </div>
            </div>
            """
        )

        with gr.Tabs(elem_classes="main-tabs"):
            with gr.Tab("✦ AI Assistant"):
                gr.Markdown("## Ask naturally\n<span class='section-copy'>The assistant selects an MCP tool and shows the decision trace.</span>")
                with gr.Row(equal_height=True):
                    with gr.Column(scale=7, elem_classes="panel"):
                        chatbot = gr.Chatbot(
                            value=[], type="messages", label="Conversation", height=470,
                            layout="bubble", placeholder="Ask about your notes, weather, or what to study.",
                            show_copy_button=True, elem_id="assistant-chatbot",
                        )
                        with gr.Row():
                            chat_input = gr.Textbox(
                                label="Your message", placeholder="What did I say about the project deadline?",
                                lines=2, scale=8, autofocus=True,
                            )
                            send_btn = gr.Button("Send ↗", variant="primary", scale=1)
                        with gr.Row():
                            gr.Examples(
                                examples=[
                                    ["Remember that the project deadline is Friday"],
                                    ["What did I say about the project deadline?"],
                                    ["What's the weather in Tokyo?"],
                                    ["What should I study in Python?"],
                                ],
                                inputs=[chat_input], label="Try an example",
                            )
                            clear_btn = gr.Button("Clear chat", size="sm")
                    with gr.Column(scale=4, elem_classes="panel"):
                        router_status = gr.Markdown(f"**Router:** {router_name} · **MCP:** ready")
                        with gr.Accordion("Tool decision", open=True):
                            decision = gr.Markdown(
                                "### MCP tool decision\nYour selected tool and arguments will appear here.",
                                elem_classes="tool-trace",
                            )
                        gr.Markdown("### Recent MCP activity")
                        activity_table = gr.Dataframe(
                            headers=ACTIVITY_HEADERS, value=[], datatype=["str"] * 5,
                            interactive=False, wrap=True, max_height=280,
                        )

            with gr.Tab("▣ Memory Notes"):
                gr.Markdown("## Persistent memory\n<span class='section-copy'>Create, search, edit, and delete notes stored through the MCP server.</span>")
                note_status = gr.HTML(_status("Memory controls are ready."))
                with gr.Row(equal_height=True):
                    with gr.Column(scale=4, elem_classes="panel"):
                        gr.Markdown("### Add a note")
                        note_content = gr.Textbox(label="Content", lines=5, placeholder="The project deadline is Friday at 5 PM.")
                        note_tags = gr.Textbox(label="Tags", placeholder="project, deadline")
                        save_btn = gr.Button("Save to memory", variant="primary")
                        gr.Markdown("### Find notes")
                        with gr.Row():
                            search_query = gr.Textbox(label="Search", placeholder="deadline", scale=4)
                            search_btn = gr.Button("Search", scale=1)
                        refresh_btn = gr.Button("Refresh all notes")
                    with gr.Column(scale=7, elem_classes="panel"):
                        notes_table = gr.Dataframe(
                            headers=NOTE_HEADERS, value=[], datatype=["str"] * 5,
                            interactive=False, wrap=True, max_height=370,
                        )
                        gr.Markdown("### Edit selected note")
                        note_selector = gr.Dropdown(label="Note ID", choices=[], filterable=True)
                        edit_content = gr.Textbox(label="Updated content", lines=3)
                        edit_tags = gr.Textbox(label="Updated tags")
                        with gr.Row():
                            update_btn = gr.Button("Update note", variant="primary")
                            delete_btn = gr.Button("Delete note", variant="stop")

            with gr.Tab("☁ Weather Dashboard"):
                gr.Markdown("## Live data connector\n<span class='section-copy'>Fetch real-time conditions through the MCP weather tool.</span>")
                with gr.Row():
                    weather_location = gr.Textbox(label="City or location", value="Bengaluru", scale=5)
                    weather_btn = gr.Button("Get current weather", variant="primary", scale=1)
                gr.Examples(examples=[["Bengaluru"], ["Tokyo"], ["London"], ["New York"]], inputs=[weather_location], label="Popular locations")
                weather_output = gr.HTML(_status("Choose a location to see live conditions."))
                with gr.Accordion("Structured MCP response", open=False):
                    weather_json = gr.JSON(value={})

            with gr.Tab("✓ Study Planner"):
                gr.Markdown("## Build a focused study plan\n<span class='section-copy'>Choose a subject and track the suggested MCP learning path.</span>")
                with gr.Row(equal_height=True):
                    with gr.Column(scale=4, elem_classes="panel"):
                        study_subject = gr.Dropdown(
                            choices=[("Python", "python"), ("Mathematics", "math"), ("Artificial Intelligence", "ai"), ("DBMS", "dbms"), ("Computer Networks", "networks")],
                            value="python", label="Subject",
                        )
                        study_btn = gr.Button("Generate study plan", variant="primary")
                        progress_status = gr.Markdown("**Progress:** Generate a plan to begin")
                    with gr.Column(scale=7, elem_classes="panel"):
                        study_plan = gr.Markdown("### Your learning path will appear here")
                        study_checklist = gr.CheckboxGroup(label="Mark topics complete", choices=[], elem_id="study-checklist")

        gr.HTML('<div class="footer-note">Local application · No data is uploaded by the UI · MCP messages travel over stdio</div>')

        chat_event = send_btn.click(
            chat_submit, [chat_input, chatbot, activity_state],
            [chat_input, chatbot, decision, router_status, activity_state, activity_table],
            show_progress="minimal",
        )
        chat_input.submit(
            chat_submit, [chat_input, chatbot, activity_state],
            [chat_input, chatbot, decision, router_status, activity_state, activity_table],
            show_progress="minimal",
        )
        clear_btn.click(clear_chat, outputs=[chatbot, decision, router_status])

        save_btn.click(
            save_note_ui, [note_content, note_tags, activity_state],
            [note_content, note_tags, notes_table, note_selector, notes_state, note_status, activity_state, activity_table],
        )
        search_btn.click(
            search_notes_ui, [search_query, activity_state],
            [notes_table, note_selector, notes_state, note_status, activity_state, activity_table],
        )
        search_query.submit(
            search_notes_ui, [search_query, activity_state],
            [notes_table, note_selector, notes_state, note_status, activity_state, activity_table],
        )
        refresh_btn.click(
            refresh_notes, [activity_state],
            [notes_table, note_selector, notes_state, note_status, activity_state, activity_table],
        )
        note_selector.change(choose_note, [note_selector, notes_state], [edit_content, edit_tags])
        update_btn.click(
            update_note_ui, [note_selector, edit_content, edit_tags, activity_state],
            [notes_table, note_selector, notes_state, note_status, activity_state, activity_table],
        )
        delete_btn.click(
            delete_note_ui, [note_selector, activity_state],
            [notes_table, note_selector, notes_state, edit_content, edit_tags, note_status, activity_state, activity_table],
        )

        weather_btn.click(
            weather_ui, [weather_location, activity_state],
            [weather_output, weather_json, activity_state, activity_table],
        )
        weather_location.submit(
            weather_ui, [weather_location, activity_state],
            [weather_output, weather_json, activity_state, activity_table],
        )

        study_btn.click(
            study_ui, [study_subject, activity_state],
            [study_plan, study_checklist, progress_status, activity_state, activity_table],
        )
        study_subject.change(
            study_ui, [study_subject, activity_state],
            [study_plan, study_checklist, progress_status, activity_state, activity_table],
        )
        study_checklist.change(update_progress, [study_checklist, study_subject], [progress_status])

        demo.load(
            refresh_notes, [activity_state],
            [notes_table, note_selector, notes_state, note_status, activity_state, activity_table],
            show_progress="hidden",
        )

    return demo


demo = build_app()


if __name__ == "__main__":
    demo.queue(default_concurrency_limit=4).launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=os.getenv("MCP_UI_NO_BROWSER") != "1",
        share=False,
        show_error=True,
    )
