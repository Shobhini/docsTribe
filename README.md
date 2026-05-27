# Docstribe Medical Notes Processor

A full-stack system that accepts uploaded medical notes, processes them asynchronously using a distributed task queue, and returns structured output — lab test orders, radiology requests, and follow-up actions — grouped by type.

Built with FastAPI, Celery, Redis, PostgreSQL, and Next.js. All services run in Docker.

---

## Architecture

```
User uploads file
       │
       ▼
  FastAPI (api)
  ├── validates file type + size
  ├── extracts raw text (OCR if image/PDF)
  ├── saves Note to PostgreSQL (status=pending)
  └── enqueues coordinator_task → Redis
                    │
                    ▼
           Celery Worker (worker)
           coordinator_task
           ├── sets status=processing
           └── chord() — fans out 3 parallel tasks:
               ├── lab_extraction_task      ─┐
               ├── radiology_extraction_task  ├─► all succeed → on_extraction_complete
               └── followup_extraction_task ─┘         │
                                                        ▼
                                              sets status=completed
                                              saves extracted tasks → PostgreSQL
                    │
                    ▼
  Next.js (frontend)
  polls /api/notes/{id}/status every 3s
  fetches results when completed
  displays grouped output
```

**Services:**

| Service | Technology | Port |
|---------|-----------|------|
| `api` | FastAPI + Uvicorn | 8000 |
| `worker` | Celery 5 | — |
| `db` | PostgreSQL 15 | 5432 |
| `redis` | Redis 7 | 6379 |
| `frontend` | Next.js 14 | 3000 |
| `flower` | Celery Flower | 5555 |

---

## Quick Start

**Prerequisites:** Docker and Docker Compose

```bash
git clone <repo-url>
cd docsTribe
docker compose up --build -d
docker compose exec api alembic upgrade head
```

| URL | What it is |
|-----|-----------|
| http://localhost:3000 | Upload UI |
| http://localhost:8000/docs | FastAPI interactive docs (Swagger) |
| http://localhost:5555 | Flower — real-time Celery task monitor |

### Run Tests

```bash
docker compose exec api python -m pytest tests/ -v
```

---

## Screenshots

**Upload page**

<img width="1093" alt="Upload page" src="https://github.com/user-attachments/assets/1b416f04-2b3a-4542-bf53-b00f89bce3f8" />

**Results page**

<img width="1233" alt="Results page" src="https://github.com/user-attachments/assets/02901718-b71d-45c6-88e1-6f90398e4c7a" />

**Flower dashboard — after processing one note (5 tasks, all succeeded)**

<img width="1222" alt="Flower dashboard" src="https://github.com/user-attachments/assets/b96359f4-2cd0-496a-88a8-9f76e205e3a2" />

---

## How It Works

### 1. File Upload (`POST /api/notes/upload`)

- Validates file extension: `.txt`, `.pdf`, `.png`, `.jpg`, `.jpeg`
- Rejects files larger than **10 MB** (HTTP 413)
- Extracts raw text:
  - `.txt` — read directly
  - `.pdf` — converted to images via `pdf2image`, then OCR via `pytesseract`
  - `.png` / `.jpg` — OCR via `pytesseract`
- Saves a `Note` record to PostgreSQL with `status=pending`
- Enqueues `coordinator_task` to Celery via Redis
- Stores the Celery task ID (`celery_task_id`) in the notes table for traceability
- Returns `note_id` immediately — does not wait for processing

### 2. Async Processing (Celery chord)

`coordinator_task` runs in the background worker:
- Sets `status=processing`, records `processing_started_at`
- Dispatches 3 tasks in **parallel** using `chord()`:
  - `lab_extraction_task` — matches keywords: CBC, HbA1c, LFT, blood test, creatinine, etc.
  - `radiology_extraction_task` — matches keywords: X-ray, MRI, CT scan, ultrasound, etc.
  - `followup_extraction_task` — matches keywords: follow up, refer to, appointment, review, etc.
- Each task uses sentence-level splitting + keyword matching (no LLM required)
- Each task checks for existing results before inserting — safe to retry
- When all 3 complete, `on_extraction_complete` (chord callback) sets `status=completed` and records `completed_at`

### 3. Retry & Failure Handling

- Every extraction task retries up to **3 times** with exponential backoff:
  - Retry 1: wait 60s
  - Retry 2: wait 120s
  - Retry 3: wait 240s
- After 3 failures, `status=failed` and `failed_at` is recorded
- If the chord dispatch itself fails (Redis down after DB commit), status is set to `failed` immediately

### 4. Frontend Polling

- After upload, the browser navigates to `/results/{note_id}`
- Polls `GET /api/notes/{id}/status` every 3 seconds using `setInterval`
- Stops polling when status is `completed` or `failed`
- Fetches and displays results grouped into Lab Tests, Radiology, Follow-ups

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/notes/upload` | Upload a medical note (multipart/form-data) |
| `GET` | `/api/notes/{id}/status` | Get current processing status + timestamps |
| `GET` | `/api/notes/{id}/results` | Get extracted tasks grouped by type |
| `GET` | `/api/notes/` | List all uploaded notes |
| `GET` | `/health` | Health check |

**Status response includes:**
```json
{
  "note_id": "533312e3-...",
  "status": "completed",
  "uploaded_at": "2026-05-27T08:43:35",
  "processing_started_at": "2026-05-27T08:43:35",
  "completed_at": "2026-05-27T08:43:35",
  "celery_task_id": "c8e6bc96-..."
}
```

---

## Database Schema

**`notes` table**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `filename` | String | Original uploaded filename |
| `raw_text` | Text | Extracted text content |
| `status` | Enum | `pending` / `processing` / `completed` / `failed` |
| `uploaded_at` | DateTime | When the note was uploaded |
| `processing_started_at` | DateTime | When the worker picked it up |
| `completed_at` | DateTime | When extraction finished successfully |
| `failed_at` | DateTime | When the note was marked failed |
| `celery_task_id` | String | Celery task ID for Flower traceability |

**`extracted_tasks` table**

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `note_id` | UUID (FK) | References `notes.id` |
| `task_type` | Enum | `lab_test` / `radiology` / `followup` |
| `description` | Text | Extracted sentence |
| `created_at` | DateTime | When the row was inserted |

Unique constraint on `(note_id, task_type, description)` — database-level deduplication.

---

## Observability

**Flower** (`http://localhost:5555`) shows:
- Which workers are online
- Tasks processed / succeeded / failed / retried per worker
- Individual task history: UUID, arguments, state, received time, start time, runtime
- Live view — upload a file and watch the 5 tasks appear in real time

**Structured logs** (visible in `docker compose logs worker`):
```
coordinator_task started note_id=533312e3-...
coordinator_task dispatched chord note_id=533312e3-...
lab_extraction_task starting note_id=533312e3-...
lab_extraction_task completed note_id=533312e3-... found=4
on_extraction_complete note_id=533312e3-... duration=0.05s
```

---

## Project Structure

```
docsTribe/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, logging config
│   │   ├── models.py            # SQLAlchemy ORM models (Note, ExtractedTask)
│   │   ├── schemas.py           # Pydantic response schemas
│   │   ├── database.py          # DB engine, session factory, Base
│   │   ├── celery_app.py        # Celery instance + config
│   │   ├── file_reader.py       # txt/pdf/image → raw text
│   │   ├── routes/
│   │   │   └── notes.py         # All API route handlers
│   │   ├── tasks/
│   │   │   ├── coordinator.py   # Entry point task, chord dispatch
│   │   │   ├── lab.py           # Lab test extraction task
│   │   │   ├── radiology.py     # Radiology extraction task
│   │   │   ├── followup.py      # Follow-up extraction task
│   │   │   └── completion.py    # Chord callback — marks completed
│   │   └── extractors/
│   │       ├── base.py          # Sentence splitter + keyword matcher
│   │       ├── lab.py           # Lab keyword list
│   │       ├── radiology.py     # Radiology keyword list
│   │       └── followup.py      # Follow-up keyword list
│   ├── alembic/
│   │   └── versions/            # Database migrations
│   ├── tests/                   # pytest suite (21 tests)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── pages/
│   │   ├── index.js             # Upload page
│   │   └── results/[note_id].js # Results page with polling
│   └── Dockerfile
├── docker-compose.yml
├── sample_note.txt              # Example medical note for testing
└── .env.example
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn |
| Task Queue | Celery 5 (chord pattern) |
| Message Broker + Result Backend | Redis 7 |
| Database | PostgreSQL 15 |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| OCR | pytesseract + pdf2image + Pillow |
| Frontend | Next.js 14 + Tailwind CSS |
| Containerization | Docker Compose (6 services) |
| Task Monitoring | Flower |
| Testing | pytest (21 tests) |

UI
<img width="1222" height="719" alt="image" src="https://github.com/user-attachments/assets/b96359f4-2cd0-496a-88a8-9f76e205e3a2" />

Step 1: Upload the sample file.
<img width="1093" height="622" alt="image" src="https://github.com/user-attachments/assets/1b416f04-2b3a-4542-bf53-b00f89bce3f8" />

Step 2: Results after processing.
<img width="1233" height="764" alt="image" src="https://github.com/user-attachments/assets/02901718-b71d-45c6-88e1-6f90398e4c7a" />

Queue Dashboard
<img width="1457" height="474" alt="image" src="https://github.com/user-attachments/assets/cdceb2a5-0364-471e-b327-00045ba54ee3" />
