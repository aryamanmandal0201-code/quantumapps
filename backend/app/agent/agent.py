"""The agent loop: send the conversation to the LLM, run any tools it asks for, repeat until it answers."""
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import groq
from groq.types.chat import ChatCompletion
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import User
from .tools import ToolContext

log = logging.getLogger("taskpilot.agent")

MAX_STEPS = 6  # max LLM round-trips per user message, so a confused model can't loop forever


class AgentError(Exception):
    """A failure we can explain to the user in plain words."""


SYSTEM_PROMPT = """You are TaskPilot, an assistant that manages the user's to-do tasks using tools.

Today is {weekday}, {today}. This week runs from today until Sunday {week_end}.
The user is {name} (role: {role}).

Rules:
- Use tools for every read or change. Never claim you changed something unless a tool returned ok.
- Convert relative dates ("Friday", "tomorrow", "next week") to YYYY-MM-DD using today's date. A weekday name means the next one on or after today.
- When the user refers to a task by name, call list_tasks (with a search term) to find its id first. If several tasks match and it's unclear which one, ask.
- A message can contain several requests. Do all of them before replying.
- delete_task only asks for confirmation. Tell the user to confirm the deletion with the button shown under your reply.
- If a tool returns an error, fix the arguments and try again, or explain the problem.
- Reply in one to three short sentences saying what you did. Don't show task ids or raw JSON.
- You only manage tasks. Politely decline unrelated requests.{admin_note}"""

ADMIN_NOTE = """
- As an admin you can also list users, list tasks across users, and assign tasks to other users by email."""


def _system_prompt(user: User) -> str:
    tz = ZoneInfo(get_settings().app_timezone)
    today = datetime.now(tz).date()
    week_end = today + timedelta(days=6 - today.weekday())
    return SYSTEM_PROMPT.format(
        weekday=today.strftime("%A"),
        today=today.isoformat(),
        week_end=week_end.isoformat(),
        name=user.name,
        role=user.role,
        admin_note=ADMIN_NOTE if user.role == "admin" else "",
    )


def make_client() -> groq.Groq:
    settings = get_settings()
    if not settings.groq_api_key:
        raise AgentError("The AI assistant isn't configured on the server yet (missing GROQ_API_KEY).")
    return groq.Groq(api_key=settings.groq_api_key, timeout=30.0, max_retries=2)


def _complete(client: groq.Groq, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> ChatCompletion:
    """One LLM call, with errors translated into friendly messages."""
    model = get_settings().groq_model
    for attempt in range(2):
        try:
            return client.chat.completions.create(
                model=model, messages=messages, tools=tools, tool_choice="auto", temperature=0.2, max_tokens=1024
            )
        except groq.BadRequestError as exc:
            # Open models occasionally produce a malformed tool call ("tool_use_failed"). One retry usually fixes it.
            log.warning("Groq bad request (attempt %s): %s", attempt + 1, exc)
            if attempt == 0:
                continue
            raise AgentError("The AI got confused by that request. Try rephrasing it a little more simply.")
        except groq.RateLimitError:
            raise AgentError("The AI service is busy right now (free-tier rate limit). Wait a few seconds and try again.")
        except groq.APITimeoutError:
            raise AgentError("The AI service took too long to answer. Please try again.")
        except groq.AuthenticationError:
            log.error("Groq rejected the API key")
            raise AgentError("The AI service isn't available right now because of a server configuration problem.")
        except (groq.APIConnectionError, groq.APIStatusError) as exc:
            log.error("Groq error: %s", exc)
            raise AgentError("The AI service is unavailable right now. Please try again in a moment.")
    raise AgentError("The AI service is unavailable right now. Please try again in a moment.")  # not reached


def run_agent(
    db: Session, user: User, message: str, history: list[dict[str, str]], client: groq.Groq
) -> dict[str, Any]:
    """Returns {reply, tool_calls, pending_actions, tasks_changed}. Raises AgentError if nothing could be done.

    `client` is injected (FastAPI dependency in production, a fake in tests)."""
    ctx = ToolContext(db, user)
    messages: list[dict[str, Any]] = [{"role": "system", "content": _system_prompt(user)}, *history, {"role": "user", "content": message}]
    trace: list[dict[str, Any]] = []
    reply: str | None = None

    for _ in range(MAX_STEPS):
        try:
            response = _complete(client, messages, ctx.tool_schemas)
        except AgentError as exc:
            if not trace:
                raise
            # Some tools already ran, so report what happened instead of hiding it behind an error.
            reply = f"I made some changes (listed below), but then hit a problem: {exc}"
            break

        msg = response.choices[0].message
        if not msg.tool_calls:
            reply = (msg.content or "").strip()
            break

        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            outcome = ctx.run(tc.function.name, tc.function.arguments)
            trace.append(
                {"name": tc.function.name, "arguments": outcome["arguments"], "ok": outcome["ok"], "summary": outcome["summary"]}
            )
            payload = {"ok": True, **outcome["result"]} if outcome["ok"] else {"ok": False, "error": outcome["error"]}
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(payload, default=str)})

    if reply is None:
        reply = "That took more steps than I'm allowed. Here is what I managed to do; try splitting the request up."
    if not reply:
        reply = "Done." if trace else "Sorry, I didn't get that. Could you rephrase?"

    return {
        "reply": reply,
        "tool_calls": trace,
        "pending_actions": ctx.pending_actions,
        "tasks_changed": ctx.tasks_changed,
    }
