# Developer Experience (DX) & Local Setup Guide

Welcome to the HireAI Developer Onboarding workspace. Follow this guide to get productive in 15 minutes.

## 1. Quick Startup

To run the local backend server:

```powershell
# 1. Install dependencies
pip install -r requirements.txt

# 2. Setup local environment configurations
cp .env.example .env

# 3. Apply database migration upgrades
cd apps/api
python -m alembic upgrade head

# 4. Start local FastAPI dev server
python -m uvicorn app.main:app --reload --port 8000
```

The REST API dashboard will be interactive at: http://127.0.0.1:8000/docs.

## 2. Seed Data & Demo Organization

Run the seed script to prepare a default workspace organization, sample leads, and agent configurations:

```powershell
python scripts/seed_development.py
```

## 3. Mock Providers & CRM

To prevent running up third-party costs or setting up complex integrations locally, HireAI routes actions through mock components under local environment modes (`ENV=development`):
- **Email:** Diverts to console outputs or template-based file saves instead of SMTP delivery requests.
- **LLMs:** Redirects to fake/stub provider models returning predefined tool payloads or chat responses.

## 4. Run Benchmarks

Run the profiling suit to compare latency baselines:

```powershell
python scripts/measure_performance.py
```
This updates [performance_baseline.json](file:///d:/abhim/Projects/HireAI/docs/performance_baseline.json).
