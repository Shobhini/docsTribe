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
               ├── lab_extraction_task       ─┐
               ├── radiology_extraction_task  ├─► all succeed → on_extraction_complete
               └── followup_extraction_task  ─┘         │
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

## Authentication

All note endpoints are protected with **JWT (JSON Web Token)** authentication.

### Flow

```
Register / Login
      │
      ▼
POST /api/auth/register  ──►  { access_token, token_type }
POST /api/auth/login     ──►  { access_token, token_type }
      │
      ▼
Client stores token in localStorage
      │
      ▼
Every API request sends:
Authorization: Bearer <token>
      │
      ▼
FastAPI get_current_user() dependency
├── extracts token from Authorization header
├── verifies JWT signature + expiry
└── returns User from DB — or raises HTTP 401
```

### Auth Endpoints

| Method | Endpoint | Body | Description |
|--------|----------|------|-------------|
| `POST` | `/api/auth/register` | `{ name, email, password }` | Create account, returns JWT |
| `POST` | `/api/auth/login` | form: `username` + `password` | Login, returns JWT |

### Register example

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Shobhini", "email": "you@example.com", "password": "yourpassword"}'
```

### Login example

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -d "username=you@example.com&password=yourpassword"
```

Both return:
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```

### Using the token

```bash
curl http://localhost:8000/api/notes/ \
  -H "Authorization: Bearer eyJ..."
```

### How it works

- **Password hashing:** `passlib` with `bcrypt` — passwords are one-way hashed, never stored in plain text
- **JWT signing:** `python-jose` with `HS256` algorithm. Payload contains `sub` (user ID), `email`, `name`, `exp` (expiry)
- **Token expiry:** 24 hours
- **User scoping:** Notes are tied to `user_id`. Users can only see and access their own notes — even if they know another note's UUID
- **Stateless:** No server-side session storage. The token is verified mathematically on every request

### Database schema — `users` table

| Column | Type | Description |
|--------|------|-------------|
| `id` | UUID (PK) | Auto-generated |
| `name` | String | Display name shown in the UI |
| `email` | String (unique) | Login credential |
| `hashed_password` | String | bcrypt hash — never the plain password |
| `is_active` | Boolean | Account active flag |
| `created_at` | DateTime | Registration timestamp |

### Testing auth in Swagger UI

1. Open `http://localhost:8000/docs`
2. Click **Authorize** (top right)
3. Enter your email as `username` and your password
4. Click **Authorize** — all subsequent requests in the docs will include the token automatically

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
| `user_id` | UUID (FK) | References `users.id` — owner of this note |

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
│   │   ├── models.py            # SQLAlchemy ORM models (User, Note, ExtractedTask)
│   │   ├── schemas.py           # Pydantic response schemas
│   │   ├── database.py          # DB engine, session factory, Base
│   │   ├── celery_app.py        # Celery instance + config
│   │   ├── file_reader.py       # txt/pdf/image → raw text
│   │   ├── auth.py              # JWT creation, password hashing, get_current_user dependency
│   │   ├── routes/
│   │   │   ├── auth.py          # Register + login endpoints
│   │   │   └── notes.py         # Note endpoints (all protected)
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
│   │   ├── login.js             # Login + register page
│   │   ├── index.js             # Upload page (protected, shows username)
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
| Authentication | JWT (python-jose) + bcrypt (passlib) |
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

---

## Design Decisions & Tradeoffs

### Why rule-based extraction instead of an LLM?

Rule-based keyword matching was chosen deliberately:
- **Deterministic** — same input always produces the same output, easy to test and debug
- **No cost** — no API credits, no rate limits, no latency from external calls
- **No hallucination** — the extractor only returns sentences that actually exist in the note
- **Architecture is LLM-ready** — the extractor functions (`extract_lab_tests`, `extract_radiology`, `extract_followups`) are isolated behind a simple interface. Swapping them for an LLM call requires changing only those functions — zero changes to the API, worker, or database

### Why Celery chord instead of sequential tasks?

Lab tests, radiology, and follow-up extraction are fully independent — they read the same text and write to separate rows. Running them sequentially would mean waiting for task 1 to finish before starting task 2, wasting time. A `chord()` fans them out in parallel and fires a callback only when all three complete. For larger notes this can cut processing time by 2-3x.

### Why polling instead of WebSockets?

Polling every 3 seconds is acceptable because:
- Notes process in under 1 second — users rarely wait through more than one poll cycle
- Simpler frontend code with no persistent connection management
- No additional infrastructure (no WebSocket server or pub/sub layer)

WebSocket would be the right upgrade if processing times grew to 30+ seconds.

### Why JWT instead of sessions?

Sessions require a shared store (Redis or DB) that every API instance must read from. This breaks horizontal scaling — if request 1 hits server A and request 2 hits server B, server B doesn't know about server A's sessions. JWT is self-contained and verified mathematically, with no shared state. Any API instance can validate any token independently.

### Why Redis for both broker and result backend?

Redis is operationally simple — one service, already required as the Celery broker. The result backend is needed specifically for `chord()` to know when all subtasks are done. In production, RabbitMQ (more durable, better routing) as broker and PostgreSQL (persistent results) as backend would be the right split.

### Why store `celery_task_id` in the notes table?

When a note gets stuck in `processing` state, you need a way to find what happened. Storing the Celery task ID lets you look it up directly in Flower or query Celery's result backend to see exactly which retry it's on, what the error was, and which worker handled it. Without it, debugging distributed failures is guesswork.

### Why `nullable=True` on `user_id` in notes?

Existing rows in the database were inserted before authentication was added. Setting `nullable=False` on the migration would fail on those rows. The migration uses `nullable=True` to keep backward compatibility, with the application enforcing ownership at the query level (`filter(Note.user_id == current_user.id)`).

---

## Known Limitations

| Limitation | Details |
|------------|---------|
| JWT revocation | Tokens remain valid until expiry even after logout. No blacklist. Production fix: short-lived tokens (15 min) + refresh token flow |
| `localStorage` for token | Accessible to JavaScript — vulnerable to XSS. Production fix: HttpOnly secure cookies |
| Single Redis instance | No persistence, no HA. If Redis restarts, queued tasks are lost. Production fix: Redis AOF persistence or RabbitMQ |
| Local filesystem uploads | Files stored in a Docker volume. Not accessible across multiple API instances. Production fix: S3 or GCS |
| OCR accuracy | Depends on image quality. Low-resolution or handwritten notes may produce poor text extraction |
| Rule-based extraction | Keyword matching misses paraphrased or unusual phrasing. Production fix: LLM-based extraction |
| No refresh tokens | Access token expires in 24h, user must log in again. Production fix: refresh token endpoint |
| Single Celery worker | No concurrency config. High load would queue up. Production fix: `--concurrency=N` or multiple worker containers |

---

## Future Improvements

| Improvement | Why |
|-------------|-----|
| Replace polling with WebSockets | Real-time updates without repeated HTTP requests |
| Refresh token flow | Short-lived access tokens + long-lived refresh tokens for better security |
| S3/GCS for file storage | Scalable, durable, accessible across multiple API instances |
| LLM-based extraction | Higher accuracy, handles paraphrasing and unusual medical terminology |
| Prometheus + Grafana | Metrics for request latency, queue depth, extraction success rate |
| Kubernetes deployment | Auto-scaling workers based on queue depth |
| Queue separation | Dedicated queues for OCR (CPU-heavy) vs text extraction (lightweight) |
| Rate limiting | Prevent abuse on upload and auth endpoints |

---

## Screenshots
UI
<img width="1222" height="719" alt="image" src="https://github.com/user-attachments/assets/b96359f4-2cd0-496a-88a8-9f76e205e3a2" />

Step 1: Upload the sample file.
<img width="1093" height="622" alt="image" src="https://github.com/user-attachments/assets/1b416f04-2b3a-4542-bf53-b00f89bce3f8" />

Step 2: Results after processing.
<img width="1233" height="764" alt="image" src="https://github.com/user-attachments/assets/02901718-b71d-45c6-88e1-6f90398e4c7a" />

Queue Dashboard
<img width="1457" height="474" alt="image" src="https://github.com/user-attachments/assets/cdceb2a5-0364-471e-b327-00045ba54ee3" />
