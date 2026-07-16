# HireAI - AI Employee Platform

HireAI is an autonomous, multi-tenant AI Employee Platform designed to automate CRM interactions, manage leads, schedule tasks, run custom automated workflows, and orchestrate stateful AI Sales agents.

---

## 🚀 Architecture Overview

HireAI is built using a decoupled monorepo structure:
- **Backend (`apps/api`)**: A high-performance, async FastAPI service handling business logic, database state, automated schedulers, and the AI agent runtime.
- **Frontend (`apps/web`)**: A modern, interactive Next.js application built with TypeScript, React, TailwindCSS, and Shadcn/UI components.
- **ADR Documentation (`docs/adr`)**: Architectural Decision Records detailing design rationales, conventions, and future plans.

---

## 🛠️ Technology Stack

### Backend
* **Core Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Python 3.11+)
* **Database & ORM**: PostgreSQL, [SQLAlchemy 2.0](https://www.sqlalchemy.org/) (Async via `asyncpg` for web runtime, Sync via `psycopg` for migrations)
* **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
* **Security & Auth**: Pydantic v2 (Validation), `pwdlib` (Argon2id password hashing), PyJWT (JSON Web Tokens), `slowapi` (Rate Limiting)
* **AI Engine**: [LiteLLM](https://github.com/BerriAI/litellm) / OpenAI SDK

### Frontend
* **Core Framework**: [Next.js 15](https://nextjs.org/) (App Router, React 19)
* **Styling**: TailwindCSS, Shadcn/UI, Lucide icons
* **Language**: TypeScript

---

## 🏛️ Core Modules & Design (ADRs)

Our core modules align with the Architecture Decision Records (ADRs) defined under `docs/adr/`:

1. **JWT & Session Design (ADR-001)**: Implements database-backed `user_sessions` with sliding-session rotation. The token payload contains a session ID (`sid`) rather than an organization ID to allow seamless multi-org switching without token reissuance.
2. **Multi-Tenant Isolation (ADR-002 & ADR-003)**: Uses tenant partitioning across all tables via a `ForeignKey("organizations.id")` to isolate org-specific records and configurations.
3. **Workflow Automation (ADR-007)**: A highly decoupled execution engine that runs conditional workflows (triggers -> conditions -> actions). Includes condition operators, action handlers, snapshot-based audit replayability, and independent execution step commits.
4. **Scheduler & Reminder Engine (ADR-008)**: An in-process background runner that uses Postgres row-level locking (`FOR UPDATE SKIP LOCKED`) to ensure concurrency safety. Processes timezone-aware cron intervals (with `croniter`) and queues notifications.
5. **Communication System (ADR-009)**: Manages automated templates and notification dispatch queues (SMS, Email, WhatsApp) with built-in provider fallback logic and delivery tracing.
6. **AI Agent Runtime (ADR-010)**: Sets up stateful conversations, memory storage, prompt management, tools execution registry, and vector-backed document retrieval.

---

## 📂 Project Structure

```
hireai/
├── apps/
│   ├── api/             # FastAPI backend
│   │   ├── app/
│   │   │   ├── api/     # API routes (v1/auth, v1/leads, etc.)
│   │   │   ├── core/    # Global settings, security, and exceptions
│   │   │   ├── db/      # Database session setup and Base class
│   │   │   ├── models/  # SQLAlchemy models
│   │   │   ├── schemas/ # Pydantic response/request schemas
│   │   │   ├── services/# Business logic services (Auth, Workflow, etc.)
│   │   │   └── utils/   # Reusable helpers (validators, parsers)
│   │   └── alembic/     # Migration scripts
│   └── web/             # Next.js frontend app
├── docs/
│   └── adr/             # Architecture Decision Records (ADRs)
├── docker-compose.yml   # Multi-service local orchestrator
└── requirements.txt     # Monorepo dependencies list
```

---

## ⚡ Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ (with npm, yarn, or pnpm)
- PostgreSQL running locally or in Docker

### 1. Backend Setup (`apps/api`)

1. Navigate to the backend directory:
   ```bash
   cd apps/api
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure environment variables. Copy `.env.example` to `.env` and configure:
   ```env
   APP_NAME=HireAI
   APP_ENV=development
   APP_DEBUG=true

   # Async URL for the FastAPI app
   DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/hireai
   # Sync URL for Alembic migrations
   DATABASE_URL_SYNC=postgresql+psycopg://postgres:postgres@localhost:5432/hireai

   SECRET_KEY=dev_secret_key_placeholder
   REFRESH_SECRET_KEY=dev_refresh_secret_key_placeholder
   OPENAI_API_KEY=your-openai-api-key
   ```
5. Run migrations:
   ```bash
   alembic upgrade head
   ```
6. Start the development server:
   ```bash
   uvicorn app.main:app --reload
   ```
   *The API documentation will be available at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).*

### 2. Frontend Setup (`apps/web`)

1. Navigate to the frontend directory:
   ```bash
   cd apps/web
   ```
2. Install Node packages:
   ```bash
   npm install
   ```
3. Start the Next.js development server:
   ```bash
   npm run dev
   ```
   *The frontend application will be running at [http://localhost:3000](http://localhost:3000).*

---

## 🧪 Testing

To run backend validation tests (e.g. testing the signup, locking, session auditing, and rotation chains):
```bash
# Set Python path to apps/api and run the script
$env:PYTHONPATH="."; python C:\Users\abhim\.gemini\antigravity-ide\brain\d57a92c8-89d7-4ca0-8466-986e0dcf430b\scratch\test_flows.py
```
