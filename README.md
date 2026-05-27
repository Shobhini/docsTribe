# Docstribe Medical Notes Processor

A full-stack system that accepts uploaded medical notes/prescriptions, processes them asynchronously, and extracts structured tasks: lab tests, radiology orders, and follow-ups.

## Architecture

```
Upload → FastAPI → Redis → Celery coordinator_task
                              ├── lab_extraction_task       ┐
                              ├── radiology_extraction_task ├─ chord() → on_complete → status=completed
                              └── followup_extraction_task  ┘
                                        ↓
                                   PostgreSQL
```

**5 Docker services:** `api` (FastAPI), `worker` (Celery), `db` (PostgreSQL), `redis`, `frontend` (Next.js)

## Quick Start

### Prerequisites
- Docker & Docker Compose installed

### Run

```bash
git clone <repo-url>
cd docsTribe
cp .env.example .env
docker-compose up --build -d
docker-compose exec api alembic upgrade head
```

- **Frontend:** http://localhost:3000
- **API docs:** http://localhost:8000/docs

### Run Tests

```bash
docker-compose exec api python -m pytest tests/ -v
```

## How It Works

1. **Upload** a `.txt`, `.pdf`, `.jpg`, or `.png` file via the UI
2. File text is extracted (OCR for images/PDFs via pytesseract)
3. A Celery `coordinator_task` is triggered asynchronously
4. Three parallel tasks fan out via `chord()`:
   - `lab_extraction_task` — scans for lab test keywords (CBC, HbA1c, LFT, etc.)
   - `radiology_extraction_task` — scans for imaging keywords (X-ray, MRI, CT scan, etc.)
   - `followup_extraction_task` — scans for follow-up keywords (follow up, review in, refer to, etc.)
5. Results are saved to PostgreSQL
6. Frontend polls `/api/notes/{id}/status` every 3 seconds
7. Once `completed`, results are displayed grouped by type

## Async Processing & Retry Logic

- Celery `coordinator_task` reads the note and fans out to 3 parallel subtasks using `chord()`
- `chord()` fires a callback (`on_extraction_complete`) only when **all 3** subtasks succeed
- Failed tasks retry with **exponential backoff**: 60s → 120s → 240s (max 3 retries)
- After 3 failed retries, note status is set to `failed`
- Coordinator task also guards chord dispatch — sets `failed` if Redis dispatch fails after DB commit

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/notes/upload` | Upload a medical note file |
| GET | `/api/notes/{id}/status` | Check processing status |
| GET | `/api/notes/{id}/results` | Get extracted tasks |
| GET | `/api/notes/` | List all uploaded notes |
| GET | `/health` | Health check |

## Project Structure

```
docsTribe/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app entry point
│   │   ├── models.py            # SQLAlchemy ORM models
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── database.py          # DB session + engine setup
│   │   ├── celery_app.py        # Celery configuration
│   │   ├── file_reader.py       # txt/pdf/image text extraction
│   │   ├── routes/notes.py      # API route handlers
│   │   ├── tasks/               # Celery task definitions
│   │   └── extractors/          # Keyword-based extraction logic
│   └── tests/                   # pytest test suite (21 tests)
├── frontend/
│   └── pages/                   # Next.js pages
├── docker-compose.yml
└── .env.example
```

## Known Limitations / Future Work

| What | Why not included | How to add |
|------|-----------------|------------|
| WebSocket live updates | Polling is simpler and sufficient | Replace `setInterval` with `socket.io` or FastAPI WebSocket |
| LLM-based extraction | No API credits available | Swap `extract_*` functions — architecture unchanged |
| Authentication | Out of scope for assignment | Add FastAPI JWT middleware |
| Unit tests for tasks | Requires Redis mock setup | Use `celery.contrib.pytest` |
| Single Redis instance | HA not required here | Add Redis Sentinel/Cluster |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Task Queue | Celery 5 |
| Message Broker | Redis 7 |
| Database | PostgreSQL 15 |
| OCR | pytesseract + pdf2image |
| Frontend | Next.js 14 + Tailwind CSS |
| Containerization | Docker Compose |
| Testing | pytest (21 tests) |

UI
<img width="1222" height="719" alt="image" src="https://github.com/user-attachments/assets/b96359f4-2cd0-496a-88a8-9f76e205e3a2" />

Step 1: Upload the sample file.
<img width="1093" height="622" alt="image" src="https://github.com/user-attachments/assets/1b416f04-2b3a-4542-bf53-b00f89bce3f8" />

Step 2: Results after processing.
<img width="1233" height="764" alt="image" src="https://github.com/user-attachments/assets/02901718-b71d-45c6-88e1-6f90398e4c7a" />
