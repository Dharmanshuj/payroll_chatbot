# Payroll Chatbot

An AI HR/payroll assistant. Employees log in and ask natural-language questions about their own salary, attendance and company policies; an admin account can ask the same kind of questions across all employees, and register new employees or update attendance from a dashboard. Answers come from an LLM agent that decides which internal tool to call rather than a fixed set of report screens.

## Live deployment

| Part | URL |
|---|---|
| Frontend (dashboard, chat, login) | https://agentic-payroll-assistant.vercel.app |
| FastAPI backend | https://payroll-chatbot-wyp5.onrender.com |
| Spring Boot MCP server | https://payroll-spring-mcp.onrender.com |

**Demo admin login** (username / password): `Admin` / `admin123`

**Demo user login** (username / password): `EMP001` / `Welcome@123`

> These are not hardcoded in source, they're read from the `ADMIN_USERNAME` / `ADMIN_PASSWORD` environment variables on both backend services (see [Environment variables](#environment-variables)). They're written here in plain text for demo convenience, since this is a portfolio/demo project. If this app is ever used with real employee data, rotate them and stop publishing them in this file.
>
> Both backend services are on Render's free tier, which sleeps after ~15 minutes of no traffic. A GitHub Actions workflow (`.github/workflows/keep-alive.yml`) pings both every 10 minutes to keep them warm; the first request after a gap can still take 20-40s if it catches a cold start anyway.

## What it does

- **Employee chat**: ask about your own profile, attendance (by month/year), salary breakdown and in-hand pay, or company policy questions (leave, reimbursement, benefits) answered from the actual policy PDFs.
- **Admin chat**: the same conversational interface, but scoped to all employees, employee lists, full salary structures, monthly attendance + payroll metrics.
- **Admin dashboard forms**: register a new employee, update an employee's monthly attendance.
- **Auth**: JWT-based login for employees (password checked against an argon2 hash) and a separate admin login, both issued by the FastAPI backend and honored by both backends.

## How a question gets answered

1. The Next.js frontend sends the chat message and JWT to the **FastAPI** backend (`POST /ask-me/stream`, server-sent events).
2. A **LangGraph** state graph runs: a *supervisor* node classifies the question, then routes it to one of three specialist nodes:
   - `payroll_node` - the employee's own data (ReAct agent, calls tools autonomously)
   - `admin_node` - all-employee data (ADMIN only)
   - `policy_node` - RAG over the HR policy PDFs (no tool loop, single retrieval + answer)
3. Tool calls for structured data (employee profile, attendance, salary) go out over **MCP (Model Context Protocol)** to the separate **Spring Boot** service, which is the only thing that talks to Postgres for that data. Policy questions instead retrieve from a **FAISS** vector index built from the PDFs in `documents/`.
4. The final answer streams back to the browser.

The two backends exist because the payroll data model (JPA entities, salary calculation, attendance rules) lives in Spring Boot as an MCP tool server, while the conversational/agentic layer (LangGraph, Gemini, RAG) lives in Python. The frontend talks to both directly for different things: FastAPI for chat/login, Spring Boot directly for the two admin dashboard forms.

## Tech stack, and why

### Backend - conversational AI (Python)

| Technology | Version | Why |
|---|---|---|
| Python | 3.12 (Docker) / 3.14 (dev) | Docker pinned to 3.12 for broad wheel availability across the heavier ML dependencies below |
| FastAPI | 0.141.1 | Async web framework for the chat/auth API, plays well with streaming responses |
| Uvicorn | 0.53.0 | ASGI server FastAPI runs on |
| LangChain | 1.4.0 | LLM/prompt/tool abstractions |
| LangGraph | 1.2.11 | The supervisor + specialist-node routing graph described above; a plain chain isn't enough once the app needs to branch by intent and loop on tool calls |
| langchain-google-genai | 4.4.0 | Gemini chat + embeddings via LangChain's interface |
| Google Gemini | `gemini-3.5-flash-lite` (chat), `gemini-embedding-001` (embeddings) | Pinned to a dated model rather than a `-latest` alias on purpose, a `-latest` alias silently moved to a model with only a 20-request/day free quota mid-project; Flash Lite gives 500/day and is plenty capable for structured tool-calling |
| FAISS (faiss-cpu) | 1.15.0 | Local vector index for the policy-document RAG lookup, no external vector DB needed for a handful of PDFs |
| psycopg2-binary | 2.9.13 | Postgres driver, used directly (no ORM) for the small set of read queries the Python side still needs |
| mcp | 2.2.0 (pinned) | Client SDK for calling the Spring Boot MCP server; pinned because a version bump previously changed the shape of a return value and broke every tool call silently |
| passlib\[argon2] / argon2-cffi | 1.7.4 / 25.1.0 | Employee password hashing |
| PyJWT | 2.14.0 | Issuing/verifying login JWTs |

### Backend - payroll data & tools (Java)

| Technology | Version | Why |
|---|---|---|
| Java | 17 | LTS, required by the Spring Boot version in use |
| Spring Boot | 3.4.5 | REST + JPA + Security in one place for the data-owning service |
| Spring AI MCP Server (webmvc) | 1.1.0 (Spring AI BOM) | Exposes the payroll/attendance/salary queries as MCP tools over Streamable HTTP, so the Python agent calls them like any other tool instead of the Python side needing its own copy of the salary-calculation logic |
| Spring Data JPA / Hibernate | (Boot-managed) | Employee/Attendance/SalaryPayment entities, with `@PrePersist`/`@PreUpdate` hooks that compute HRA/EPF/gross/net pay from basic salary automatically |
| HikariCP | (Boot-managed) | Connection pooling; tuned (see `application.properties`) specifically because Neon's serverless Postgres auto-suspends after ~5 min idle, and the defaults let the pool hold onto since-killed connections |
| PostgreSQL driver | (Boot-managed) | Talks to the same Neon database as the Python side |
| jjwt | 0.12.6 | Validates JWTs issued by the Python side (shared `SECRET_KEY`) so a request authenticated once works against both services |
| Maven (via `mvnw`) | wrapper 3.3.4, Maven 3.9.14 | No local Maven install needed, the wrapper downloads it |

### Database

| Technology | Why |
|---|---|
| PostgreSQL (Neon, serverless) | Employee, attendance and salary_payment tables. Originally MySQL, migrated to Postgres mid-project (`database/postgres_setup.sql` has the full schema + seed data) |

### Frontend

| Technology | Version | Why |
|---|---|---|
| Next.js | 16.0.10 | App Router dashboard, chat UI, login, admin forms |
| React | 19.2.0 | Paired with the above |
| Tailwind CSS | 4.x | Styling |
| Radix UI (shadcn-style components) | pinned per-package in `package.json` | Accessible primitives (dialogs, dropdowns, tabs, etc.) behind the dashboard's UI |

### Infrastructure

| Technology | Why |
|---|---|
| Docker (multi-stage) | One `Dockerfile` per backend (root = FastAPI, `demo/` = Spring Boot), so either can be deployed as a container on Render without a language runtime being pre-installed on the host |
| Render | Hosts both backend containers (free tier) |
| Vercel | Hosts the Next.js frontend |
| GitHub Actions | Scheduled workflow pings both `/health` endpoints every 10 minutes to fight Render's free-tier sleep |

## Project structure

```
payroll_chatbot/
├── app.py                    # FastAPI app: CORS, /health, mounts chat_routes
├── api/
│   └── chat_routes.py        # /login, /ask-me/stream, /debug-routes
├── agents/
│   └── agents.py             # LangGraph graph: supervisor + payroll/admin/policy nodes
├── tools/
│   ├── mcp_tool.py           # Calls the Spring Boot MCP server (employee/attendance/salary tools)
│   ├── document_tool.py      # search_documents tool, backed by rag/retriever.py
│   └── database_tool.py      # (legacy) direct-SQL versions of some tools
├── rag/
│   └── retriever.py          # Loads the prebuilt FAISS index for policy Q&A
├── ingestion/ + ingest.py     # One-off pipeline: PDFs -> chunks -> embeddings -> vector_store/
├── documents/                 # Source HR policy PDFs (leave, reimbursement, benefits, ...)
├── vector_store/              # Prebuilt FAISS index (committed, so the API doesn't need to run ingestion at boot)
├── database/
│   ├── db.py                  # psycopg2 connection helper
│   └── postgres_setup.sql     # Full schema + seed data for a fresh Postgres/Neon database
├── security/                   # Field-level access policy, masking, audit logging, query validation
├── services/                   # auth_services.py (hashing/JWT), security_service.py (get_current_user dependency)
├── tests/                      # manual verification scripts (see Tests section, not pytest)
├── Dockerfile, .dockerignore   # FastAPI container
├── demo/                       # Spring Boot MCP server (separate Maven project)
│   ├── src/main/java/com/example/demo/
│   │   ├── model/              # Employee, Attendance, SalaryPayment JPA entities
│   │   ├── controller/         # EmployeeController (admin REST endpoints), HealthController
│   │   ├── service/             # EmployeeService, PayrollToolService (the @Tool-annotated MCP methods)
│   │   ├── security/             # JwtAuthenticationFilter, JwtTokenService
│   │   └── config/               # SecurityConfig, McpToolConfig
│   ├── src/main/resources/application.properties
│   └── Dockerfile, .dockerignore # Spring Boot container (multi-stage, via mvnw)
├── frontend/Dashboard/          # Next.js app (App Router)
│   ├── app/                     # login, dashboard pages
│   └── components/              # login-form, chat-card, admin/register-form, admin/update-attendance-form, ui/*
└── .github/workflows/keep-alive.yml  # Render free-tier keep-warm ping
```

## Environment variables

**Root `.env`** (FastAPI, gitignored):

| Variable | Purpose |
|---|---|
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_SSLMODE` | Postgres/Neon connection |
| `GEMINI_API_KEY` | Google Gemini API key |
| `SECRET_KEY` | JWT signing secret - **must be identical** to the Spring Boot service's, it validates tokens issued here |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT lifetime (default 60) |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | Admin login credentials, checked in `api/chat_routes.py` |
| `SPRING_MCP_URL` | URL of the Spring Boot MCP endpoint, e.g. `https://payroll-spring-mcp.onrender.com/mcp` |
| `CORS_ORIGINS` | Comma-separated list of allowed frontend origins |

**`demo/.env`** (Spring Boot, gitignored): same `DB_*` variables, plus `ADMIN_USERNAME`/`ADMIN_PASSWORD` (its own Basic Auth admin user) and `CORS_ALLOWED_ORIGINS`. `SECRET_KEY` is deliberately *not* duplicated here; `JwtTokenService` falls back to reading it from the project root `.env` if it isn't set directly.

**`frontend/Dashboard/.env`** (gitignored):

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | FastAPI backend URL |
| `NEXT_PUBLIC_MCP_API_URL` | Spring Boot backend URL (used directly by the two admin forms) |

## Running it locally

### 1. Database

```bash
psql -U postgres -f database/postgres_setup.sql
```

Creates the `company` database, all three tables, and seeds 10 employees. Skip the `CREATE DATABASE`/`\c` lines if pointing at an already-provisioned database (e.g. Neon).

### 2. Python backend

```bash
python -m venv venv
# Windows
.\venv\Scripts\Activate.ps1
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
# create .env with the variables listed above

uvicorn app:app --reload --port 8000
```

### 3. Spring Boot MCP server

```bash
cd demo
# create demo/.env with the variables listed above
./mvnw spring-boot:run
```

Runs on port 8080 by default (`server.port=${PORT:8080}`).

### 4. Frontend

```bash
cd frontend/Dashboard
npm install
# create .env with NEXT_PUBLIC_API_URL / NEXT_PUBLIC_MCP_API_URL pointing at localhost
npm run dev
```

## Running it with Docker

```bash
# FastAPI backend, from the repo root
docker build -t payroll-chatbot-api .
docker run -p 8000:8000 --env-file .env payroll-chatbot-api

# Spring Boot MCP server, from demo/
cd demo
docker build -t payroll-mcp-server .
docker run -p 8080:8080 --env-file .env payroll-mcp-server
```

Both images read `$PORT` if the host sets it (Render does this automatically), defaulting to 8000/8080 otherwise.

## Tests

`tests/` holds standalone manual-verification scripts, not a pytest suite (`pytest` isn't even a project dependency). Each one calls its own `run_test()` and prints the result for manual inspection rather than asserting anything, run one directly:

```bash
python -m tests.test_masking
python -m tests.test_security_filter
```

`test_database_tool.py` and `test_workflow.py` currently import `query_employee_department` from `tools/database_tool.py`, a function that no longer exists there (the tools were renamed/restructured since), so those two will fail with an `ImportError` until updated to match the current tool names (`get_employee_by_id`, `get_attendance`, etc.).
