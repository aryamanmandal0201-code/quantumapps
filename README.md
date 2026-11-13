# TaskPilot: an AI agent that manages your tasks

**Project B (TaskPilot)** for the QuantumApps AI, AI Engineer (Full Stack) take-home.

TaskPilot is a to-do app you run by chatting. You type things like “Add a task to submit the monthly report by Friday” or “Mark the report done and add a task to start the next one”, and an LLM agent decides which tools to call (add, list, update, delete), runs them against the database, and tells you what it did. The task list beside the chat updates straight away. Admins can also see every user and every task, change roles, and assign tasks to other users through the agent.

## Live app

| | |
|---|---|
| Frontend | https://YOUR-APP.vercel.app |
| Backend | https://YOUR-API.onrender.com |
| API docs | https://YOUR-API.onrender.com/docs |

> The backend is on Render's free plan, which sleeps after 15 minutes without traffic. The first request after that can take about a minute while it wakes up; the app shows a “still working” notice while it waits.

### Demo logins

| Role | Email | Password |
|---|---|---|
| Admin | admin@taskpilot.demo | `YOUR-ADMIN-PASSWORD` |
| User | user@taskpilot.demo | `User@12345` |

The demo user starts with a few sample tasks. You can also sign up; new accounts always get the normal user role.

### Try this (as the demo user)

1. `Add a task to submit the monthly report by Friday`
2. `What's due this week?`
3. `Mark the report done and add a task to start the next one` (two tools in one message)
4. `Delete the insurance task` (the agent asks; you confirm with a button)

As the admin, try `Assign "Prepare the audit checklist" to user@taskpilot.demo for Monday`, then log in as the user to see it.

## Tech stack and why

| Layer | Choice | Why |
|---|---|---|
| Backend | FastAPI, SQLAlchemy 2.0, Pydantic v2 | Required framework; SQLAlchemy keeps queries explicit and lets tests run on SQLite while production uses Postgres |
| LLM | Groq, `openai/gpt-oss-120b` | Free tier, very fast, and reliable at OpenAI-style tool calling. The model name is an env var, so it can be swapped |
| Agent | Plain Python loop with the `groq` SDK | The agent is small and easy to follow, debug and explain. A framework like LangGraph would add more concepts than it saves here |
| Database | Supabase Postgres (free) | Hosted Postgres that doesn't expire like Render's free Postgres (30 days), and Render's disk is wiped on restart so a file DB wouldn't survive. Only the database is used (auth is my own), connected through Supabase's IPv4 pooler, with Row Level Security on so Supabase's auto-generated REST API can't read the tables |
| Auth | Own JWT auth (PyJWT) + Argon2id password hashing (`argon2-cffi`) | Small, no third-party account needed, every part is visible in the code; Argon2id is the current OWASP recommendation for password storage |
| Frontend | React 18 + strict TypeScript + Vite + React Router | Simple SPA, no server rendering needed. Styled after Vercel's Geist design system (Geist fonts, gray scale, hairline borders) in plain CSS, light and dark |
| Hosting | Vercel (frontend), Render (backend), Supabase (DB) | All free, no credit card |

## How the AI part works

1. The user's message goes to `POST /api/chat` with the last 10 chat messages as context.
2. The backend builds a system prompt with today's date (in `APP_TIMEZONE`) so the model can turn “Friday” or “this week” into real dates, plus rules such as “look up a task's id before changing it”.
3. The model gets tool definitions (JSON schemas): `add_task`, `list_tasks`, `update_task`, `delete_task`, plus `list_users`, `list_all_tasks` and `assign_task` for admins only.
4. The agent loop (`backend/app/agent/agent.py`) calls the model. If it asks for tools, the backend runs them, sends the results back, and calls the model again, up to 6 rounds, until the model replies in plain text. That is what makes multi-step requests work: “Mark the report done and add the next one” becomes `list_tasks` → `update_task` + `add_task` → reply.
5. If a tool fails (for example a bad date), the error goes back to the model so it can correct itself.
6. The reply, the list of tools that ran, and any pending confirmations go back to the frontend and are shown under the message.

**Safe by design.** The model never sends a user id. Each request creates a `ToolContext` bound to the logged-in user, and every tool goes through `services/tasks.py`, which always filters by `owner_id`. If the model asks to update task 42 and it belongs to someone else, the tool answers “no task with that id belongs to this user”. Admin tools are not even offered to normal users, and each one re-checks the role before running. The model can't delete anything: `delete_task` only creates a confirmation, and the real delete happens when the user clicks the button.

## How login and roles work

- Sign up and log in at `/api/auth/signup` and `/api/auth/login`. Passwords are hashed with **Argon2id**; the plain password is never stored.
- Login returns a signed JWT (HS256, 24 hour expiry) that the frontend sends as `Authorization: Bearer …`.
- `get_current_user` (`backend/app/deps.py`) checks the token and loads the user **from the database on every request**, so the role always comes from the database, not the token. A role change takes effect immediately.
- Every route under `/api/admin` has a `require_admin` dependency. A normal user calling it directly gets `403`.
- The sign-up schema has no `role` field. Even if someone sends `"role": "admin"`, the account is a normal user.
- The first admin is created separately, on startup, from the `ADMIN_EMAIL` / `ADMIN_PASSWORD` environment variables. After that, admins can promote or demote other users (not themselves).
- The frontend hides the Admin page and link for normal users, but that is only convenience; the backend enforces everything.

| | User | Admin |
|---|---|---|
| Manage own tasks (chat or list) | ✓ | ✓ |
| See all users and all tasks | | ✓ |
| Change another user's role | | ✓ |
| Assign a task to another user (via the agent) | | ✓ |

## Extra features (beyond the minimum)

- **Action log under every reply**: each tool the agent called, whether it worked, and what it did (“Marked “Submit the monthly report” as done”).
- **Confirmation before deleting**: the agent can only *request* a deletion; the user confirms with a button. Enforced in the backend, not just the prompt.
- **Admin task assignment through the agent**; the assignee sees “From Admin” on the task.
- **Admin dashboard**: users with open/done counts, role changes, all tasks filtered by owner and status.
- **Priorities and due dates**, with overdue and due-soon highlighting.
- **Persistent chat history** per user, with a “Clear chat” button.
- **Changed tasks flash briefly** in the list after the agent edits them.
- **Manual controls too**: tick, delete or add a task without the agent.
- **Friendly errors**: rate limits, timeouts, a missing API key and database outages return plain-language messages; failed chat messages have a “Try again” button; a notice explains slow first requests on the free server. If the LLM fails halfway, the reply still lists the changes already made.
- **Tests** (18, pytest): role enforcement, Argon2id hashing, duplicate sign-ups, cross-user access through both the REST API and the agent's tools, admin-tool isolation, delete confirmation, input validation, and full chat-endpoint and multi-step agent runs against a fake LLM (no API key needed).
- Light and dark themes, keyboard focus styles, mobile layout.

## Run it locally

You need Python 3.11+ and Node 18+.

**Backend**

```bash
cd backend
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                # then fill in GROQ_API_KEY, JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD
python -m scripts.seed              # optional: demo user and sample tasks
uvicorn app.main:app --reload       # http://localhost:8000/docs
pytest                              # run the tests
```

Without `DATABASE_URL` it uses a local SQLite file, which is fine for development.

**Frontend**

```bash
cd frontend
npm install
cp .env.example .env                # VITE_API_URL=http://localhost:8000
npm run dev                         # http://localhost:5173
npm run build                       # type-checks (tsc, strict) and builds
```

## Deploying (what I did)

1. **Supabase**: create a project, then *Connect* → *Session pooler* and copy the URI (`postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres`). Use the pooler, not the direct connection: the direct one is IPv6-only and Render's free plan can't reach it. The app creates its tables on first start.
2. **Render**: New → Blueprint → this repo (uses `render.yaml`), or a Web Service with root `backend`, build `pip install -r requirements.txt`, start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `DATABASE_URL`, `GROQ_API_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` and `CORS_ORIGINS` (the Vercel URL). `JWT_SECRET` is generated by Render.
3. **Seed** the demo user from your machine: put the Supabase `DATABASE_URL` in `backend/.env` and run `python -m scripts.seed` (Render's free plan has no shell).
4. **Vercel**: import the repo, root directory `frontend`, set `VITE_API_URL` to the Render URL. `vercel.json` makes page refreshes on `/admin` work.
5. Open the live app in a private window and log in with both demo accounts.

## Project structure

```
backend/
  app/
    main.py              app setup, CORS, error handlers, startup
    config.py            settings from environment variables
    database.py          engine and session
    models.py            User, Task, ChatMessage (+ allowed roles/priorities/statuses)
    schemas.py           request/response models
    security.py          Argon2id hashing and JWT
    deps.py              injected dependencies: get_db, get_current_user, require_admin, get_llm_client
    bootstrap.py         first admin + Row Level Security on startup
    services/            business logic and queries (no HTTP)
      tasks.py           task queries, always scoped by owner
      users.py           sign-up, login check, roles
      chat.py            stored chat history
    agent/
      tools.py           tool schemas and handlers (bound to one user)
      agent.py           system prompt and the tool-calling loop
    routers/             thin HTTP layer: auth, tasks, chat, admin
  scripts/seed.py        demo user and sample tasks
  tests/                 pytest suite
frontend/
  src/
    types.ts             TypeScript mirrors of the API schemas
    api/                 all HTTP calls (client.ts + auth, tasks, chat, admin)
    auth.tsx             login state
    pages/               AuthPage, Workspace, AdminPage
    components/          ChatPanel, TaskPanel, NavBar, Segmented, WakeBanner
```

## Not finished / could be improved

- **Free-tier sleep.** Supabase pauses a free project after about a week with no database activity (it can be resumed from the dashboard); normal use keeps it awake.
- **No database migrations.** Tables are created with `create_all` on startup. A real project should use Alembic.
- **Token storage.** The JWT is kept in `localStorage`, which is simple but exposed to XSS. An httpOnly cookie with CSRF protection would be safer. There is no refresh token or logout-everywhere.
- **No rate limiting** on login or chat, and no password reset or email verification.
- **Replies aren't streamed**; the user waits for the whole agent loop.
- **Model limits.** Open models occasionally produce a malformed tool call. The backend retries once and then shows a friendly message. The free tier also has rate limits.
- **Time zone** is one server-wide setting (`APP_TIMEZONE`), not per user.
- Tests run on SQLite, not Postgres; there are no frontend tests yet (the frontend is type-checked on every build).
