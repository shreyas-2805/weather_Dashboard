"""Interactive client for the Personal Assistant and Data Dashboard labs.

It starts ``server.py`` over MCP stdio and uses a transparent local router to
choose a tool. This keeps the experiment reproducible without requiring an
API key; the router is the small stand-in for an LLM tool-selection step.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

from mcp import Client, StdioServerParameters


SERVER_PATH = Path(__file__).with_name("server.py")
LOCAL_ENV_PATH = Path(__file__).with_name(".env")


def load_local_env() -> None:
    """Load project-only settings without overwriting real environment variables."""
    if not LOCAL_ENV_PATH.exists():
        return
    for raw_line in LOCAL_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


load_local_env()


def configured_router_name() -> str:
    if not os.getenv("OPENAI_API_KEY"):
        return "Local router"
    if "groq.com" in os.getenv("OPENAI_BASE_URL", "").lower():
        return "Groq LLM"
    return "OpenAI LLM"


def text_from_result(result) -> str:
    """Collect text blocks from an MCP CallToolResult."""
    return "\n".join(block.text for block in result.content if block.type == "text")


def choose_tool_local(request: str) -> tuple[str, dict, str]:
    """Return (tool, arguments, explanation) for a natural-language request."""
    lowered = request.lower().strip()
    weather_match = re.search(r"(?:weather|temperature|forecast).*?\bin\s+(.+?)(?:\?|$)", lowered)
    if weather_match:
        location = weather_match.group(1).strip(" .")
        return "get_current_weather", {"location": location}, f"This looks like a live-weather question, so I will call get_current_weather(location='{location}')."
    if any(word in lowered for word in ("study", "learn", "subject", "revise", "revision")):
        subject = next((name for name in ("python", "math", "ai", "dbms", "networks") if name in lowered), "")
        return "suggest_study", {"subject": subject}, "This asks for study guidance, so I will call suggest_study."
    if any(word in lowered for word in ("remember", "save note", "save this", "note that")):
        content = re.sub(r"^(remember|save note|save this|note that)[:\s]*", "", request, flags=re.I).strip()
        return "save_note", {"content": content or request, "tags": "conversation"}, "This is new information to remember, so I will call save_note."
    search_match = re.search(r"\babout\s+(.+?)(?:\?|$)", request, flags=re.I)
    search_match = re.search(r"(?:about|for)\s+(.+?)(?:\?|$)", lowered)
    query = search_match.group(1).strip(" .") if search_match else request
    return "search_notes", {"query": query}, "This asks what was said earlier, so I will call search_notes(query)."


def choose_tool_with_openai(request: str, api_key: str) -> tuple[str, dict, str]:
    """Use an OpenAI-compatible endpoint when OPENAI_API_KEY is configured."""
    prompt = (
        "Choose exactly one MCP tool for the user's request. Return only JSON with "
        "keys tool, arguments, explanation. Allowed tools: save_note(content,tags), "
        "search_notes(query), get_current_weather(location), suggest_study(subject).\n"
        f"User request: {request}"
    )
    payload = json.dumps({
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    req = Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 MCP-Lab/1.0",
        },
        method="POST",
    )
    with urlopen(req, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    decision = json.loads(body["choices"][0]["message"]["content"])
    allowed = {"save_note", "search_notes", "get_current_weather", "suggest_study"}
    if decision.get("tool") not in allowed or not isinstance(decision.get("arguments"), dict):
        raise ValueError("The model returned an invalid tool decision")
    return decision["tool"], decision["arguments"], decision.get("explanation", "The model selected this tool.")


async def choose_tool_with_mode(request: str) -> tuple[str, dict, str, str]:
    """Choose a tool and report whether an LLM or local router was used."""
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            tool, arguments, explanation = await asyncio.to_thread(choose_tool_with_openai, request, api_key)
            return tool, arguments, explanation, configured_router_name()
        except Exception as exc:
            print(f"[assistant] LLM router unavailable ({exc}); using the local router.")
    tool, arguments, explanation = choose_tool_local(request)
    return tool, arguments, explanation, "Local router"


async def choose_tool(request: str) -> tuple[str, dict, str]:
    tool, arguments, explanation, _mode = await choose_tool_with_mode(request)
    return tool, arguments, explanation


def pretty_answer(tool: str, raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    if tool == "get_current_weather" and "error" not in data:
        return (
            f"Current weather in {data['location']}: {data['temperature_c']} deg C "
            f"({data['condition']}), feels like {data['feels_like_c']} deg C, "
            f"humidity {data['humidity_percent']}%."
        )
    return json.dumps(data, indent=2, ensure_ascii=False)


async def call(client: Client, tool: str, arguments: dict) -> str:
    result = await client.call_tool(tool, arguments)
    if result.is_error:
        raise RuntimeError(text_from_result(result))
    return text_from_result(result)


async def natural_query(client: Client, request: str) -> None:
    tool, arguments, explanation = await choose_tool(request)
    print(f"\n[assistant] Decision: {explanation}")
    print(f"[tool] {tool}({arguments})")
    raw = await call(client, tool, arguments)
    print("[assistant] Answer:")
    print(pretty_answer(tool, raw))


async def menu(client: Client) -> None:
    print("Personal Assistant + Data Dashboard")
    print("Type a natural question, or choose a command below.")
    while True:
        request = input("\nYou (q to quit): ").strip()
        if request.lower() in {"q", "quit", "exit"}:
            return
        if request:
            await natural_query(client, request)


async def demo(client: Client) -> None:
    """Run both experiments once, useful for testing and screenshots."""
    print("[demo] Expt 1: CRUD memory")
    saved = json.loads(await call(client, "save_note", {"content": "The project deadline is Friday.", "tags": "project,deadline"}))
    note_id = saved["note"]["id"]
    print(pretty_answer("save_note", json.dumps(saved)))
    print(pretty_answer("search_notes", await call(client, "search_notes", {"query": "deadline"})))
    print(pretty_answer("update_note", await call(client, "update_note", {"note_id": note_id, "content": "The project deadline is Friday at 5 PM.", "tags": "project,deadline"})))
    print(pretty_answer("delete_note", await call(client, "delete_note", {"note_id": note_id})))
    print("\n[demo] Expt 2: live data connector")
    await natural_query(client, "What's the weather in Tokyo?")
    await natural_query(client, "What should I study in Python?")


async def run(args: argparse.Namespace) -> None:
    server = StdioServerParameters(command=sys.executable, args=[str(SERVER_PATH)])
    async with Client(server) as client:
        if args.query:
            await natural_query(client, args.query)
        elif args.demo:
            await demo(client)
        else:
            await menu(client)


def main() -> None:
    parser = argparse.ArgumentParser(description="MCP lab client")
    parser.add_argument("--query", help="Ask one natural-language question")
    parser.add_argument("--demo", action="store_true", help="Run a CRUD and weather smoke test")
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
