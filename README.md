# workspace-agent

An AI agent that reads job-related emails from Gmail and acts on them: logs new opportunities to a spreadsheet, add interview invites to your calendar, and drafts replies for human approval before sending.

A self-learning project for understanding how to build production-shaped LLM agents with safety gates, structured state machines, and Google Workspace integrations.

## What it does

For each new email in your inbox:

| Email type | What the agent does |
|---|---|
| Job invite / posting | Extracts company, role, apply link, etc. and appends to a Google Sheet |
| Interview invite | Extracts date, time, meeting link and creates an event on your Google Calendar |
| Recruiter asks (needs reply) | Drafts a reply in Gmail, waits for your approval, then sends |
| Anything else | Ignores |

Sends are gated behind a CLI approval step — the agent never emails anyone on your behalf without you reviewing the draft first.

## Architecture

```
Gmail inbox
   │
   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│  Ingestion   │ -> │Classification│ -> │   Planning   │ -> │ Auto execute │ -> │  Approved    │
│              │    │              │    │              │    │              │    │  execute     │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
   fetch email        LLM classifies      LLM extracts        sheet append /      send email
   parse MIME         into 4 categories   structured fields   calendar event /    after HITL
   HTML → Markdown                        create Action row   gmail draft         approval
   store in SQLite
```

### Database
State lives in SQLite - `messages` tracks emails and `actions` tracks actions associated with emails.\
Each row in `messages` flows through statuses: `FETCHED → CLASSIFIED → PLANNED → ACTIONED`. Each row in `actions` carries the structured payload for action execution and flows through its own statuses: `PENDING → EXECUTED` (auto-approved) or `AWAITING_APPROVAL → APPROVED → EXECUTED` (gated).

## Stack

- **Python 3.12** + **uv** for dependency management
- **SQLAlchemy 2 + Alembic** for ORM and DB migrations over **SQLite**
- **Pydantic** for schema validation at every LLM boundary
- **LangChain + Anthropic Claude** (Sonnet / Haiku) for classification, extraction, and reply drafting
- **google-api-python-client** for Gmail, Calendar, Sheets

## Project layout

```
app/
├── core/                       # cross-cutting concerns
│   ├── config.py               # pydantic-settings, reads .env
│   ├── database.py             # SQLAlchemy session + Base
│   ├── google_auth.py          # OAuth credentials + token refresh
│   ├── logging_config.py       # stderr + app.log + agent.jsonl
│   ├── models.py               # Message, Action, Attachment
│   ├── profile.py              # user profile loader (for drafter)
│   └── schemas.py              # Pydantic schemas for LLM outputs
├── pipeline/
│   ├── orchestrator.py         # end-to-end pipeline driver
│   ├── ingestion/              # Gmail fetch + parse
│   ├── classification/         # LLM categorizer
│   ├── planning/               # per-category extractors → actions
│   └── execution/
│       ├── execute.py          # executor for auto-approved (PENDING actions)
│       ├── approve.py          # gated executor (APPROVED only)
│       ├── _common.py          # shared dispatcher
│       └── handlers/           # one per side effect: gmail, calendar, sheet
├── cli/
│   └── approve_pending.py      # interactive HITL approval
└── utils/                      # formatter, html_to_markdown
alembic/                        # migrations
resources/
├── logs/                       # app.log, agent.jsonl
├── sqlite/app.db
└── profile.yaml                # static user context for drafter
```

## Setup

### Prerequisites

- Python 3.12+
- A Google account (personal or Workspace)
- An Anthropic API key

### 1. Install

```bash
git clone <repo>
cd workspace-agent
uv sync
```

### 2. Google Cloud + OAuth

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com)
2. Enable: **Gmail API**, **Google Calendar API**, **Google Sheets API**, **Google Drive API**
3. Configure the **OAuth consent screen**:
   - User Type: **External** (use this even if you see a pseudo-org for your personal account)
   - Add your email under **Test users**
   - Scopes: `gmail.readonly`, `gmail.send`, `gmail.compose`, `calendar`, `spreadsheets`
4. Create **OAuth client ID** → application type **Desktop app** → download as `credentials.json` and place at the repo root

On first pipeline run, a browser will open for the OAuth handshake. A `token.json` will be cached for subsequent runs.

### 3. Environment

Create `.env` at the repo root:

```env
ANTHROPIC_API_KEY=sk-ant-...

# SQLite database file
SQLITE_DATABASE_URI=sqlite:///resources/sqlite/app.db

# Where job-apply emails are appended
SPREADSHEET_ID=<your google sheet id>
SPREADSHEET_RANGE=A2:H

# Timezone for created calendar events (IANA name)
DEFAULT_TIMEZONE=Asia/Kolkata

# User profile YAML
PROFILE_PATH=resources/profile.yaml
```

### 4. User profile

The drafter needs context about you. Create `resources/profile.yaml`:

```yaml
name: Your Name
current_role: Senior Engineer
years_experience: 8
location: San Francisco
timezone: America/Los_Angeles
availability: weekdays after 5 PM PT
salary_expectations_response: |
  Flexible on compensation; happy to discuss specifics once I learn more about scope.
tone: friendly but professional
signature: |
  Best,
  Your Name
attachments:
  resume: resources/attachments/resume.pdf
```

Place your resume PDF at the path referenced under `attachments`.

### 5. Database

```bash
uv run alembic upgrade head
```

## Running

### One pipeline pass

Runs ingestion → classification → planning → auto-execution end-to-end:

```bash
uv run python -m app.pipeline.orchestrator
```

After this, any `reply_needed` emails will have a Gmail draft created and queued for your approval.

### Approve pending sends

```bash
uv run approve
```

Interactive CLI lists each draft awaiting approval. For each:

```
[a]pprove · [r]eject · [s]kip · [e]dit in Gmail · [q]uit
```

After approvals are recorded, the gated executor sends them immediately.

### Individual stages

For debugging, each stage is runnable on its own:

```bash
uv run python -m app.pipeline.ingestion.ingest
uv run python -m app.pipeline.classification.classify
uv run python -m app.pipeline.planning.plan
uv run python -m app.pipeline.execution.execute
uv run python -m app.pipeline.execution.approve
```

## Logs

- `resources/logs/app.log` — human-readable, rotating file log of pipeline lifecycle
- `resources/logs/agent.jsonl` — structured JSON lines, one per LLM call (extractor / drafter / classifier)
- stderr — same as `app.log`, for live tailing

Query agent behavior:

```bash
# All low-confidence classifications
jq 'select(.structured_response.confidence_score < 0.7)' resources/logs/agent.jsonl

# Drafts that contain unfilled placeholders
jq 'select(.structured_response.reply_body | contains("[INSERT"))' resources/logs/agent.jsonl
```

## Migrations

Schema lives in `app/core/models.py`. After any model change:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## Gotchas

- **Personal Gmail accounts can't use OAuth "Internal".** Even if Google Cloud shows a pseudo-organization, you don't have a Workspace org with users. Use **External + Test User**.
- **`token.json` becomes stale** if you add scopes. Delete it and re-auth.
- **Gmail draft URLs in the CLI** point to the Drafts list, not a specific draft — Gmail's UI doesn't expose stable per-draft URLs without internal message IDs.

## Note

This is a personal learning project, not a production system. The code prioritizes clarity over robustness; it has no test suite and no deployment story. It does, however, ingest a real inbox, classify real emails, and send real replies — so the safety boundaries (HITL gating, draft-before-send) are non-decorative.
