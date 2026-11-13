"""Tools the AI agent can call, and the code that runs them.

Security model: the LLM only chooses *which* tool to call and with what task details.
It never supplies a user id. Every handler below is bound to the logged-in user (ToolContext.user)
and goes through services/tasks.py, which filters by owner. Admin-only tools are not even
offered to normal users, and each one re-checks the role before doing anything.
"""
import json
from datetime import date
from typing import Any, Callable

from sqlalchemy.orm import Session

from ..models import PRIORITIES, Task, User
from ..services import tasks as task_service
from ..services import users as user_service


class ToolError(Exception):
    """An error the model can read and recover from (e.g. a bad date format)."""


# ---------------------------------------------------------------------------
# Tool schemas (OpenAI-compatible JSON schema, which Groq uses)
# ---------------------------------------------------------------------------
def _fn(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


_DATE = {"type": "string", "description": "Date in YYYY-MM-DD format."}
_PRIORITY = {"type": "string", "enum": list(PRIORITIES)}

USER_TOOLS = [
    _fn(
        "add_task",
        "Create a new task for the current user.",
        {
            "title": {"type": "string", "description": "Short task title."},
            "description": {"type": "string", "description": "Optional extra detail."},
            "due_date": _DATE,
            "priority": _PRIORITY,
        },
        ["title"],
    ),
    _fn(
        "list_tasks",
        "List the current user's tasks. Use this to find a task's id before updating or deleting it, "
        "and to answer questions like 'what is due this week'.",
        {
            "status": {"type": "string", "enum": ["todo", "done", "all"], "description": "Defaults to all."},
            "due_after": {**_DATE, "description": "Only tasks due on or after this date (YYYY-MM-DD)."},
            "due_before": {**_DATE, "description": "Only tasks due on or before this date (YYYY-MM-DD)."},
            "search": {"type": "string", "description": "Text to match in the title or description."},
        },
    ),
    _fn(
        "update_task",
        "Change a task: mark it done or not done, rename it, change its due date, priority or description. "
        "Only include the fields that should change.",
        {
            "task_id": {"type": "integer"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "due_date": {"type": "string", "description": "YYYY-MM-DD, or 'none' to remove the due date."},
            "priority": _PRIORITY,
            "status": {"type": "string", "enum": ["todo", "done"]},
        },
        ["task_id"],
    ),
    _fn(
        "delete_task",
        "Request deletion of a task. This does NOT delete immediately: the user must confirm in the app.",
        {"task_id": {"type": "integer"}},
        ["task_id"],
    ),
]

ADMIN_TOOLS = [
    _fn("list_users", "Admin only. List all users with their email and role.", {}),
    _fn(
        "list_all_tasks",
        "Admin only. List tasks across all users, optionally for one user.",
        {
            "user_email": {"type": "string", "description": "Only this user's tasks."},
            "status": {"type": "string", "enum": ["todo", "done", "all"]},
        },
    ),
    _fn(
        "assign_task",
        "Admin only. Create a task for another user, identified by email.",
        {
            "assignee_email": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "due_date": _DATE,
            "priority": _PRIORITY,
        },
        ["assignee_email", "title"],
    ),
]


# ---------------------------------------------------------------------------
# Argument helpers. Models sometimes send null / "null" / "" for optional fields,
# or numbers as strings, so we normalise before validating.
# ---------------------------------------------------------------------------
def _opt(args: dict, key: str) -> Any:
    value = args.get(key)
    if value is None or (isinstance(value, str) and value.strip().lower() in ("", "null", "none")):
        return None
    return value


def _str(args: dict, key: str, max_len: int, required: bool = False) -> str | None:
    value = _opt(args, key)
    if value is None:
        if required:
            raise ToolError(f"'{key}' is required.")
        return None
    value = str(value).strip()
    if len(value) > max_len:
        raise ToolError(f"'{key}' must be at most {max_len} characters.")
    return value


def _date(args: dict, key: str) -> date | None:
    value = _opt(args, key)
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value).strip()[:10])
    except ValueError:
        raise ToolError(f"'{key}' must be a date in YYYY-MM-DD format, got {value!r}.")


def _int(args: dict, key: str) -> int:
    value = _opt(args, key)
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ToolError(f"'{key}' must be a task id number.")


def _choice(args: dict, key: str, options: tuple[str, ...]) -> str | None:
    value = _opt(args, key)
    if value is None:
        return None
    value = str(value).strip().lower()
    if value not in options:
        raise ToolError(f"'{key}' must be one of {', '.join(options)}.")
    return value


def task_to_dict(task: Task, include_owner: bool = False) -> dict:
    data = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        # Spelled out so the model doesn't have to compute weekdays (it sometimes gets them wrong).
        "due_weekday": task.due_date.strftime("%A") if task.due_date else None,
        "priority": task.priority,
        "status": task.status,
    }
    if include_owner:
        data["owner"] = task.owner.email
    return data


def _fmt_due(d: date | None) -> str:
    return f", due {d.strftime('%a %d %b')}" if d else ""


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------
class ToolContext:
    """Runs tool calls on behalf of exactly one user."""

    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.tasks_changed = False
        self.pending_actions: list[dict] = []
        self._handlers: dict[str, Callable[[dict], tuple[dict, str]]] = {
            "add_task": self._add_task,
            "list_tasks": self._list_tasks,
            "update_task": self._update_task,
            "delete_task": self._delete_task,
        }
        if self.is_admin:
            self._handlers.update(
                {
                    "list_users": self._list_users,
                    "list_all_tasks": self._list_all_tasks,
                    "assign_task": self._assign_task,
                }
            )

    @property
    def is_admin(self) -> bool:
        return self.user.role == "admin"

    @property
    def tool_schemas(self) -> list[dict]:
        return USER_TOOLS + (ADMIN_TOOLS if self.is_admin else [])

    def run(self, name: str, raw_arguments: str | None) -> dict:
        """Execute one tool call. Always returns a dict: {ok, result | error, summary, arguments}."""
        try:
            args = json.loads(raw_arguments or "{}")
            if not isinstance(args, dict):
                args = {}
        except json.JSONDecodeError:
            return {"ok": False, "error": "Tool arguments were not valid JSON.", "summary": "Invalid arguments", "arguments": {}}

        handler = self._handlers.get(name)
        if handler is None:
            return {"ok": False, "error": f"Tool '{name}' is not available.", "summary": "Tool not available", "arguments": args}
        try:
            result, summary = handler(args)
            return {"ok": True, "result": result, "summary": summary, "arguments": args}
        except ToolError as exc:
            return {"ok": False, "error": str(exc), "summary": str(exc), "arguments": args}

    def _require_admin(self) -> None:
        if not self.is_admin:  # defence in depth: these handlers aren't registered for users anyway
            raise ToolError("Only admins can use this tool.")

    # ---- user tools ----
    def _add_task(self, args: dict):
        task = task_service.create_task(
            self.db,
            owner_id=self.user.id,
            title=_str(args, "title", 200, required=True),
            description=_str(args, "description", 2000),
            due_date=_date(args, "due_date"),
            priority=_choice(args, "priority", PRIORITIES) or "medium",
        )
        self.tasks_changed = True
        return {"task": task_to_dict(task)}, f"Added “{task.title}”{_fmt_due(task.due_date)}"

    def _list_tasks(self, args: dict):
        status = _choice(args, "status", ("todo", "done", "all"))
        tasks = task_service.list_tasks(
            self.db,
            owner_id=self.user.id,
            status=None if status == "all" else status,
            due_before=_date(args, "due_before"),
            due_after=_date(args, "due_after"),
            search=_str(args, "search", 200),
        )
        return {"count": len(tasks), "tasks": [task_to_dict(t) for t in tasks]}, f"Found {len(tasks)} task(s)"

    def _get_own(self, args: dict) -> Task:
        task = task_service.get_owned_task(self.db, self.user.id, _int(args, "task_id"))
        if task is None:
            raise ToolError("No task with that id belongs to this user. Call list_tasks to find the right id.")
        return task

    def _update_task(self, args: dict):
        task = self._get_own(args)
        fields: dict[str, Any] = {}
        if (title := _str(args, "title", 200)) is not None:
            fields["title"] = title
        if (desc := _str(args, "description", 2000)) is not None:
            fields["description"] = desc
        if "due_date" in args:
            raw = args.get("due_date")
            if isinstance(raw, str) and raw.strip().lower() == "none":
                fields["due_date"] = None
            elif (due := _date(args, "due_date")) is not None:
                fields["due_date"] = due
        if (priority := _choice(args, "priority", PRIORITIES)) is not None:
            fields["priority"] = priority
        if (status := _choice(args, "status", ("todo", "done"))) is not None:
            fields["status"] = status
        if not fields:
            raise ToolError("Nothing to update: include at least one field to change.")

        task = task_service.update_task(self.db, task, fields)
        self.tasks_changed = True
        if fields.keys() == {"status"}:
            summary = f"Marked “{task.title}” as {'done' if task.status == 'done' else 'not done'}"
        else:
            summary = f"Updated “{task.title}” ({', '.join(fields)})"
        return {"task": task_to_dict(task)}, summary

    def _delete_task(self, args: dict):
        task = self._get_own(args)
        # Deletion is never done by the model. We hand it to the user as a confirmation button.
        if not any(p["task_id"] == task.id for p in self.pending_actions):
            self.pending_actions.append({"type": "delete_task", "task_id": task.id, "title": task.title})
        return (
            {"status": "awaiting_user_confirmation", "task": task_to_dict(task)},
            f"Asked to confirm deleting “{task.title}”",
        )

    # ---- admin tools ----
    def _list_users(self, args: dict):
        self._require_admin()
        users = user_service.list_users(self.db)
        data = [{"name": u.name, "email": u.email, "role": u.role} for u in users]
        return {"count": len(data), "users": data}, f"Found {len(data)} user(s)"

    def _list_all_tasks(self, args: dict):
        self._require_admin()
        owner_id = None
        email = _str(args, "user_email", 255)
        if email:
            owner = user_service.get_by_email(self.db, email)
            if owner is None:
                raise ToolError(f"No user with email {email}.")
            owner_id = owner.id
        status = _choice(args, "status", ("todo", "done", "all"))
        tasks = task_service.list_tasks(self.db, owner_id=owner_id, status=None if status == "all" else status)
        return (
            {"count": len(tasks), "tasks": [task_to_dict(t, include_owner=True) for t in tasks]},
            f"Found {len(tasks)} task(s) across users",
        )

    def _assign_task(self, args: dict):
        self._require_admin()
        email = user_service.normalize_email(_str(args, "assignee_email", 255, required=True) or "")
        assignee = user_service.get_by_email(self.db, email)
        if assignee is None:
            raise ToolError(f"No user with email {email}. Call list_users to see valid emails.")
        task = task_service.create_task(
            self.db,
            owner_id=assignee.id,
            created_by_id=self.user.id,
            title=_str(args, "title", 200, required=True),
            description=_str(args, "description", 2000),
            due_date=_date(args, "due_date"),
            priority=_choice(args, "priority", PRIORITIES) or "medium",
        )
        if assignee.id == self.user.id:
            self.tasks_changed = True
        return {"task": task_to_dict(task), "assigned_to": email}, f"Assigned “{task.title}” to {assignee.name}"
