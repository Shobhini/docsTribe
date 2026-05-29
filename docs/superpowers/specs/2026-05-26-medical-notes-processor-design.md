# Medical Notes Processor — Design Spec
**Date:** 2026-05-26  
**Project:** Docstribe AI Assignment  
**Author:** Shobhini  

---

## Overview

A full-stack system that accepts uploaded medical notes/prescriptions, processes them asynchronously using Celery workers, extracts structured tasks (lab tests, radiology tests, follow-ups), and exposes REST APIs for uploading and checking results.

**Stack:** FastAPI + Next.js + PostgreSQL + Redis + Celery + Docker Compose

---

## 1. System Architecture

5 services running in Docker Compose:

```
┌─────────────────────────────────────────────────────┐
│                   Docker Compose                      │
│                                                       │
│  ┌──────────┐    ┌───────┐    ┌──────────────────┐   │
│  │ Next.js  │───▶│FastAPI│───▶│  Redis (broker)  │   │
│  │ (3000)   │    │(8000) │    └────────┬─────────┘   │
│  └──────────┘    └───┬───┘             │              │
│                      │         ┌───────▼──────────┐   │
│                      │         │  Celery Workers   │   │
│                      │         │                   │   │
│                      │         │ coordinator_task  │   │
│                      │         │  ├─ lab_task      │   │
│                      │         │  ├─ radiology_task│   │
│                      │         │  └─ followup_task │   │
│                      │         └───────┬───────────┘   │
│                      │                 │               │
│                      └────────┐        │               │
│                               ▼        ▼               │
│                          ┌────────────────┐            │
│                          │  PostgreSQL    │            │
│                          │  (5432)        │            │
│                          └────────────────┘            │
└─────────────────────────────────────────────────────┘
```

| Service    | Image/Build        | Role                              |
|------------|--------------------|-----------------------------------|
| `db`       | postgres:15        | Persistent storage                |
| `redis`    | redis:7            | Celery message broker + backend   |
| `api`      | builds backend/    | FastAPI REST API                  |
| `worker`   | same as api        | Celery worker process             |
| `frontend` | builds frontend/   | Next.js UI                        |

---

## 2. Database Schema

```sql
-- Uploaded medical notes
notes (
  id          UUID        PRIMARY KEY,
  filename    TEXT,
  raw_text    TEXT,       -- plain text (direct or OCR-extracted)
  status      ENUM        ('pending', 'processing', 'completed', 'failed'),
  uploaded_at TIMESTAMP,
  updated_at  TIMESTAMP
)

-- Extracted task items
extracted_tasks (
  id          UUID        PRIMARY KEY,
  note_id     UUID        FOREIGN KEY → notes.id,
  task_type   ENUM        ('lab_test', 'radiology', 'followup'),
  description TEXT,
  created_at  TIMESTAMP
)
```

**Design decisions:**
- UUID primary keys — harder to enumerate than integers (basic security)
- Single `extracted_tasks` table with `task_type` column — clean, simple, sufficient
- `raw_text` stored on the note — enables re-processing without re-uploading

---

## 3. API Endpoints

| Method | Endpoint                        | Description                          |
|--------|---------------------------------|--------------------------------------|
| POST   | `/api/notes/upload`             | Upload file, trigger processing      |
| GET    | `/api/notes/{note_id}/status`   | Poll processing status               |
| GET    | `/api/notes/{note_id}/results`  | Get extracted tasks when complete    |
| GET    | `/api/notes/`                   | List all uploaded notes              |

### POST `/api/notes/upload`
- Accepts: `multipart/form-data` with file (`.txt`, `.pdf`, `.png`, `.jpg`)
- Creates `notes` row with `status=pending`
- Triggers `coordinator_task` via Celery
- Returns: `{ note_id, status }`

### GET `/api/notes/{note_id}/status`
- Returns: `{ note_id, status, uploaded_at }`
- Frontend polls every 3 seconds while `status=processing`

### GET `/api/notes/{note_id}/results`
- Returns:
```json
{
  "note_id": "uuid",
  "status": "completed",
  "tasks": {
    "lab_tests": ["CBC blood test", "Thyroid function"],
    "radiology": ["Chest X-Ray"],
    "followups": ["Review in 2 weeks"]
  }
}
```

---

## 4. Celery Task Flow

```
Upload triggers:
coordinator_task(note_id)
    ├── reads raw_text from DB
    ├── updates note status → 'processing'
    ├── launches Celery group() of 3 parallel tasks:
    │       lab_extraction_task(note_id, raw_text)
    │       radiology_extraction_task(note_id, raw_text)
    │       followup_extraction_task(note_id, raw_text)
    └── wraps in chord() with callback:
            on_all_complete(note_id) → status = 'completed'

Each subtask:
    - Runs keyword/regex extraction on raw_text
    - Inserts found items into extracted_tasks table
    - On failure: exponential backoff retries
        retry 1 → 60s
        retry 2 → 120s
        retry 3 → 240s
        after 3 retries → note status = 'failed'
```

**Key Celery primitives used:**
- `group()` — parallel task execution
- `chord()` — group + callback when ALL tasks complete
- `autoretry_for` — automatic retry on exceptions
- `max_retries=3`, `countdown` — retry delay control

---

## 5. Rule-Based Extraction

Each extractor uses keyword lists + sentence extraction:

```python
LAB_KEYWORDS = [
    "cbc", "blood test", "hemoglobin", "glucose", "lipid panel",
    "thyroid", "tsh", "hba1c", "urine test", "creatinine", "liver function"
]

RADIOLOGY_KEYWORDS = [
    "x-ray", "xray", "mri", "ct scan", "ultrasound", "sonography",
    "chest x-ray", "echocardiogram", "mammogram", "bone scan"
]

FOLLOWUP_KEYWORDS = [
    "follow up", "follow-up", "revisit", "review in", "come back",
    "return in", "next appointment", "consult", "refer to", "referral"
]
```

Extraction logic:
1. Lowercase the raw text
2. Scan for each keyword
3. Extract the full sentence containing the keyword as the description
4. Return list of found descriptions

**Extensibility note:** The extraction function can be swapped for an LLM API call without changing the Celery task architecture.

**File type handling:**
- `.txt` → read directly as string
- `.pdf` → `pdf2image` → `pytesseract` → string
- `.png/.jpg` → `pytesseract` directly → string

---

## 6. Frontend (Next.js)

**Two pages only:**

### Page 1: Upload (`/`)
- File drag-and-drop or click to select
- Accepts `.txt`, `.pdf`, `.jpg`, `.png`
- On submit: POST to `/api/notes/upload`, redirect to results page

### Page 2: Results (`/results/[note_id]`)
- On load: start polling `/api/notes/{note_id}/status` every 3 seconds
- Show spinner while `status=pending/processing`
- On `status=completed`: fetch `/api/notes/{note_id}/results`, display grouped tasks
- On `status=failed`: show error message with note_id for debugging
- Clear polling interval when terminal status reached

**Tech:** Plain `fetch`, `setInterval` for polling, Tailwind CSS for styling

---

## 7. Project Structure

```
docsTribe/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── database.py          # DB session + engine setup
│   │   ├── celery_app.py        # Celery configuration
│   │   ├── tasks/
│   │   │   ├── coordinator.py   # coordinator_task (chord orchestration)
│   │   │   ├── lab.py           # lab_extraction_task
│   │   │   ├── radiology.py     # radiology_extraction_task
│   │   │   └── followup.py      # followup_extraction_task
│   │   └── extractors/
│   │       ├── lab.py           # keyword matching logic
│   │       ├── radiology.py
│   │       └── followup.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── pages/
│   │   ├── index.js             # upload page
│   │   └── results/
│   │       └── [note_id].js     # results + polling page
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## 8. Docker Compose Setup

```yaml
services:
  db:
    image: postgres:15
    healthcheck: pg_isready

  redis:
    image: redis:7
    healthcheck: redis-cli ping

  api:
    build: ./backend
    depends_on: [db, redis]  # with healthchecks

  worker:
    build: ./backend
    command: celery -A app.celery_app worker
    depends_on: [db, redis]

  frontend:
    build: ./frontend
    depends_on: [api]
```

---

## 9. Interview Preparation

### Questions & Model Answers

**Q: Why Celery over a background thread?**  
A: Background threads die with the process, have no retry mechanism, and can't be monitored. Celery tasks are persistent in Redis, survive restarts, support retries, and can be distributed across multiple workers.

**Q: What is a message broker? Why does Celery need Redis?**  
A: A message broker is a middleman that holds task messages. The FastAPI process puts a task message into Redis. Celery workers pick it up independently. This decouples the API from the workers — neither needs to know about the other directly.

**Q: Why chord() over group()?**  
A: `group()` runs tasks in parallel with no coordination. `chord()` adds a callback that fires only when ALL tasks in the group complete successfully. I need this to know when all 3 extractors are done so I can mark the note as `completed`.

**Q: What is task idempotency and why does it matter?**  
A: An idempotent task produces the same result whether run once or multiple times. It matters for retries — if a task fails halfway and retries, it shouldn't create duplicate records. I handle this by checking if extracted_tasks already exist for a note_id before inserting.

**Q: What happens if Redis goes down?**  
A: In-flight tasks are lost. New uploads can't be processed. The API should return a 503. For production, I'd use Redis Sentinel or Cluster for HA. For this project I'd mention it as a known limitation.

**Q: Why PostgreSQL over MongoDB?**  
A: The data is structured and relational — notes have tasks, tasks belong to notes. PostgreSQL gives ACID guarantees which matter for status updates (I don't want a note marked 'completed' if some tasks failed to save). MongoDB would work too but adds no benefit here.

**Q: How would you scale to 10,000 uploads/day?**  
A: Scale horizontally — run multiple Celery worker containers (just add replicas in Docker Compose or Kubernetes). Redis handles the queue. PostgreSQL handles the data. The API is stateless so it scales too. The bottleneck would likely be the DB — add connection pooling (pgbouncer) and read replicas if needed.

**Q: A task is stuck in 'processing' for 10 minutes — how do you debug?**  
A: Check Celery worker logs first. Check Redis to see if the task message is still in the queue or was consumed. Check if the worker process is alive. Look for exceptions in the task log. If the worker crashed mid-task, the task stays 'processing' forever — I'd add a periodic cleanup job that resets notes stuck in 'processing' for over 5 minutes.

**Q: Difference between depends_on and healthcheck in Docker Compose?**  
A: `depends_on` waits for the container to START. A healthcheck waits for the service to be READY — e.g. PostgreSQL accepting connections. Without healthchecks, the API container might start before the DB is ready and crash on first DB connection.

---

## 10. Demo Walkthrough Plan (7-8 min)

1. **(0-2 min) Architecture overview** — show the diagram, explain each service, explain why fan-out
2. **(2-5 min) Code walkthrough** — show coordinator task + chord, show one extractor, show retry config, show DB models
3. **(5-7 min) Live demo** — upload a sample .txt file, watch status change in UI, show extracted results
4. **Close** — mention what you'd add with more time: WebSocket instead of polling, LLM-based extraction, auth

---

## 11. What to Mention as "Known Limitations / Future Work"
- Polling instead of WebSocket (know how to add it)
- Rule-based extraction instead of LLM (architecture supports swapping)
- No authentication (would add JWT in production)
- No unit tests (would add pytest for extractors)
- Single Redis instance (would use Sentinel for HA)

Mentioning these proactively shows maturity — you know the tradeoffs, you made deliberate choices.
