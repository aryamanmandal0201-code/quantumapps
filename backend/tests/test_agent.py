"""Agent tests with a fake LLM client, so they run without a Groq key or network."""
import json
from types import SimpleNamespace

from app.agent.agent import run_agent
from app.agent.tools import ToolContext
from app.database import SessionLocal
from app.deps import get_llm_client
from app.main import app
from app.models import User
from app.services.tasks import create_task, list_tasks

from .conftest import auth, signup


def _tool_call(call_id, name, args):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def _response(content=None, tool_calls=None):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content, tool_calls=tool_calls))])


class FakeClient:
    """Returns scripted responses in order, and records what it was sent."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _user(db, email):
    return db.query(User).filter_by(email=email).one()


def test_multi_step_request_runs_every_tool(client):
    signup(client, "multi@test.dev")
    with SessionLocal() as db:
        user = _user(db, "multi@test.dev")
        report = create_task(db, user.id, "Submit the monthly report")
        fake = FakeClient(
            [
                _response(tool_calls=[_tool_call("c1", "list_tasks", {"search": "report"})]),
                _response(
                    tool_calls=[
                        _tool_call("c2", "update_task", {"task_id": report.id, "status": "done"}),
                        _tool_call("c3", "add_task", {"title": "Start next month's report", "priority": "high"}),
                    ]
                ),
                _response(content="Marked the report as done and added the next one."),
            ]
        )
        result = run_agent(db, user, "Mark the report done and add a task to start the next one", [], client=fake)

        assert [c["name"] for c in result["tool_calls"]] == ["list_tasks", "update_task", "add_task"]
        assert all(c["ok"] for c in result["tool_calls"])
        assert result["tasks_changed"] is True
        tasks = {t.title: t for t in list_tasks(db, user.id)}
        assert tasks["Submit the monthly report"].status == "done"
        assert tasks["Start next month's report"].priority == "high"


def test_tools_cannot_reach_another_users_task(client):
    signup(client, "owner@test.dev")
    signup(client, "attacker@test.dev")
    with SessionLocal() as db:
        owner = _user(db, "owner@test.dev")
        attacker = _user(db, "attacker@test.dev")
        victim_task = create_task(db, owner.id, "Private task")

        ctx = ToolContext(db, attacker)
        out = ctx.run("update_task", json.dumps({"task_id": victim_task.id, "status": "done"}))
        assert out["ok"] is False
        out = ctx.run("delete_task", json.dumps({"task_id": victim_task.id}))
        assert out["ok"] is False
        assert ctx.pending_actions == []
        db.refresh(victim_task)
        assert victim_task.status == "todo"


def test_admin_tools_are_not_available_to_users(client):
    signup(client, "plain@test.dev")
    with SessionLocal() as db:
        ctx = ToolContext(db, _user(db, "plain@test.dev"))
        names = {t["function"]["name"] for t in ctx.tool_schemas}
        assert "assign_task" not in names and "list_users" not in names
        out = ctx.run("assign_task", json.dumps({"assignee_email": "plain@test.dev", "title": "x"}))
        assert out["ok"] is False


def test_delete_needs_confirmation(client):
    signup(client, "del@test.dev")
    with SessionLocal() as db:
        user = _user(db, "del@test.dev")
        task = create_task(db, user.id, "Old task")
        ctx = ToolContext(db, user)
        out = ctx.run("delete_task", json.dumps({"task_id": task.id}))
        assert out["ok"] is True
        assert ctx.pending_actions == [{"type": "delete_task", "task_id": task.id, "title": "Old task"}]
        assert len(list_tasks(db, user.id)) == 1  # still there until the user confirms


def test_bad_date_is_reported_back_to_the_model(client):
    signup(client, "date@test.dev")
    with SessionLocal() as db:
        ctx = ToolContext(db, _user(db, "date@test.dev"))
        out = ctx.run("add_task", json.dumps({"title": "x", "due_date": "next friday"}))
        assert out["ok"] is False and "YYYY-MM-DD" in out["error"]


def test_chat_endpoint_runs_agent_and_saves_history(client):
    token = signup(client, "chat@test.dev")["access_token"]
    fake = FakeClient(
        [
            _response(tool_calls=[_tool_call("c1", "add_task", {"title": "Buy milk"})]),
            _response(content="Added “Buy milk”."),
        ]
    )
    app.dependency_overrides[get_llm_client] = lambda: fake
    try:
        r = client.post("/api/chat", json={"message": "  Add a task to buy milk  "}, headers=auth(token))
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["tasks_changed"] is True
    assert [c["name"] for c in body["tool_calls"]] == ["add_task"]
    assert [t["title"] for t in client.get("/api/tasks", headers=auth(token)).json()] == ["Buy milk"]
    history = client.get("/api/chat/history", headers=auth(token)).json()
    assert [(m["role"], m["content"]) for m in history] == [
        ("user", "Add a task to buy milk"),
        ("assistant", "Added “Buy milk”."),
    ]


def test_blank_chat_message_is_rejected(client):
    token = signup(client, "blank@test.dev")["access_token"]
    app.dependency_overrides[get_llm_client] = lambda: FakeClient([])
    try:
        assert client.post("/api/chat", json={"message": "   "}, headers=auth(token)).status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_chat_endpoint_gives_friendly_error_without_api_key(client):
    token = signup(client, "nokey@test.dev")["access_token"]
    r = client.post("/api/chat", json={"message": "hi"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 503
    assert "isn't configured" in r.json()["detail"]
