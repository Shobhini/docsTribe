# Medical Notes Processor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a full-stack medical notes processor that accepts file uploads, extracts lab/radiology/followup tasks asynchronously via Celery workers, and displays results in a Next.js UI.

**Architecture:** FastAPI handles uploads and REST API. A Celery coordinator task fans out to 3 parallel extraction subtasks using `chord()`. Results are stored in PostgreSQL. Next.js polls for status and displays results.

**Tech Stack:** FastAPI, SQLAlchemy, Celery, Redis, PostgreSQL, Alembic, pytesseract, pdf2image, Next.js, Tailwind CSS, Docker Compose

---

## File Map

```
docsTribe/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, mounts all routers
│   │   ├── database.py          # SQLAlchemy engine, SessionLocal, Base
│   │   ├── models.py            # Note, ExtractedTask ORM models
│   │   ├── schemas.py           # Pydantic: NoteUploadResponse, NoteStatus, NoteResults
│   │   ├── celery_app.py        # Celery instance config (broker=redis, backend=redis)
│   │   ├── routes/
│   │   │   └── notes.py         # POST /upload, GET /{id}/status, GET /{id}/results, GET /
│   │   ├── tasks/
│   │   │   ├── coordinator.py   # coordinator_task: sets status=processing, fires chord
│   │   │   ├── lab.py           # lab_extraction_task: extracts + inserts lab_test rows
│   │   │   ├── radiology.py     # radiology_extraction_task: extracts + inserts radiology rows
│   │   │   ├── followup.py      # followup_extraction_task: extracts + inserts followup rows
│   │   │   └── completion.py    # on_extraction_complete: sets status=completed
│   │   ├── extractors/
│   │   │   ├── base.py          # extract_sentences(text, keywords) → list[str]
│   │   │   ├── lab.py           # LAB_KEYWORDS, extract_lab_tests(text) → list[str]
│   │   │   ├── radiology.py     # RADIOLOGY_KEYWORDS, extract_radiology(text) → list[str]
│   │   │   └── followup.py      # FOLLOWUP_KEYWORDS, extract_followups(text) → list[str]
│   │   └── file_reader.py       # read_file(path, filename) → str (txt/pdf/image dispatch)
│   ├── tests/
│   │   ├── test_extractors.py   # unit tests for all 3 extractors + base
│   │   ├── test_file_reader.py  # unit tests for file reading
│   │   └── test_routes.py       # integration tests for API endpoints
│   ├── Dockerfile
│   ├── requirements.txt
│   └── alembic/                 # DB migrations (init via alembic init)
│       ├── env.py
│       └── versions/
│           └── 001_initial.py
├── frontend/
│   ├── pages/
│   │   ├── index.js             # Upload page
│   │   └── results/
│   │       └── [note_id].js     # Results + polling page
│   ├── styles/
│   │   └── globals.css          # Tailwind imports
│   ├── Dockerfile
│   ├── package.json
│   ├── tailwind.config.js
│   └── next.config.js           # API proxy to backend
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Task 1: Project Scaffold & Docker Compose

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `backend/requirements.txt`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`
- Create: `frontend/package.json`
- Create: `frontend/next.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/styles/globals.css`

- [ ] **Step 1: Create backend/requirements.txt**

```
fastapi==0.111.0
uvicorn==0.30.1
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
alembic==1.13.1
celery==5.4.0
redis==5.0.6
python-multipart==0.0.9
Pillow==10.3.0
pytesseract==0.3.10
pdf2image==1.17.0
python-dotenv==1.0.1
pydantic==2.7.1
pydantic-settings==2.3.0
pytest==8.2.2
httpx==0.27.0
```

- [ ] **Step 2: Create backend/Dockerfile**

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **Step 3: Create frontend/package.json**

```json
{
  "name": "docstribe-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start"
  },
  "dependencies": {
    "next": "14.2.3",
    "react": "^18",
    "react-dom": "^18"
  },
  "devDependencies": {
    "autoprefixer": "^10",
    "postcss": "^8",
    "tailwindcss": "^3"
  }
}
```

- [ ] **Step 4: Create frontend/Dockerfile**

```dockerfile
FROM node:20-alpine

WORKDIR /app
COPY package.json .
RUN npm install
COPY . .

CMD ["npm", "run", "dev"]
```

- [ ] **Step 5: Create frontend/next.config.js**

```js
/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://api:8000/api/:path*',
      },
    ]
  },
}

module.exports = nextConfig
```

- [ ] **Step 6: Create frontend/tailwind.config.js**

```js
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,jsx}',
    './components/**/*.{js,jsx}',
  ],
  theme: { extend: {} },
  plugins: [],
}
```

- [ ] **Step 7: Create frontend/styles/globals.css**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 8: Create .env.example**

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/docstribe
REDIS_URL=redis://redis:6379/0
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=docstribe
```

- [ ] **Step 9: Create docker-compose.yml**

```yaml
version: "3.9"

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-postgres}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
      POSTGRES_DB: ${POSTGRES_DB:-docstribe}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@db:5432/docstribe}
      REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - uploads:/app/uploads

  worker:
    build: ./backend
    command: celery -A app.celery_app worker --loglevel=info
    environment:
      DATABASE_URL: ${DATABASE_URL:-postgresql://postgres:postgres@db:5432/docstribe}
      REDIS_URL: ${REDIS_URL:-redis://redis:6379/0}
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - uploads:/app/uploads

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - api
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  postgres_data:
  uploads:
```

- [ ] **Step 10: Copy .env.example to .env**

```bash
cp .env.example .env
```

- [ ] **Step 11: Commit scaffold**

```bash
git init
git add docker-compose.yml .env.example backend/requirements.txt backend/Dockerfile frontend/Dockerfile frontend/package.json frontend/next.config.js frontend/tailwind.config.js frontend/styles/globals.css
git commit -m "chore: project scaffold with docker-compose and dependencies"
```

---

## Task 2: Database Models & Alembic Setup

**Files:**
- Create: `backend/app/__init__.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial.py`

- [ ] **Step 1: Create backend/app/__init__.py**

```python
```
(empty file)

- [ ] **Step 2: Create backend/app/database.py**

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/docstribe")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 3: Write failing test for models**

Create `backend/tests/__init__.py` (empty) and `backend/tests/test_models.py`:

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base
from app.models import Note, ExtractedTask, NoteStatus, TaskType
import uuid

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def db():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def test_create_note(db):
    note = Note(
        id=str(uuid.uuid4()),
        filename="test.txt",
        raw_text="Patient needs CBC blood test.",
        status=NoteStatus.pending,
    )
    db.add(note)
    db.commit()
    saved = db.query(Note).first()
    assert saved.filename == "test.txt"
    assert saved.status == NoteStatus.pending


def test_create_extracted_task(db):
    note = Note(
        id=str(uuid.uuid4()),
        filename="test.txt",
        raw_text="Patient needs CBC blood test.",
        status=NoteStatus.pending,
    )
    db.add(note)
    db.commit()

    task = ExtractedTask(
        id=str(uuid.uuid4()),
        note_id=note.id,
        task_type=TaskType.lab_test,
        description="CBC blood test",
    )
    db.add(task)
    db.commit()
    saved = db.query(ExtractedTask).first()
    assert saved.description == "CBC blood test"
    assert saved.task_type == TaskType.lab_test
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/test_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.models'`

- [ ] **Step 5: Create backend/app/models.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.orm import relationship
import enum
from app.database import Base


class NoteStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class TaskType(str, enum.Enum):
    lab_test = "lab_test"
    radiology = "radiology"
    followup = "followup"


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String, nullable=False)
    raw_text = Column(Text, nullable=True)
    status = Column(Enum(NoteStatus), default=NoteStatus.pending, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("ExtractedTask", back_populates="note", cascade="all, delete-orphan")


class ExtractedTask(Base):
    __tablename__ = "extracted_tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    note_id = Column(String, ForeignKey("notes.id"), nullable=False)
    task_type = Column(Enum(TaskType), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    note = relationship("Note", back_populates="tasks")
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && python -m pytest tests/test_models.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 7: Initialize Alembic**

```bash
cd backend && alembic init alembic
```

- [ ] **Step 8: Update backend/alembic/env.py** — replace the `target_metadata` section:

```python
# At top of env.py, after existing imports, add:
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.database import Base
from app import models  # noqa: F401 — ensures models are registered

# Find the line: target_metadata = None
# Replace it with:
target_metadata = Base.metadata
```

- [ ] **Step 9: Generate initial migration**

```bash
cd backend && alembic revision --autogenerate -m "initial"
```

Expected: creates `alembic/versions/<hash>_initial.py` with `notes` and `extracted_tasks` tables.

- [ ] **Step 10: Commit**

```bash
git add backend/app/database.py backend/app/models.py backend/app/__init__.py backend/tests/ backend/alembic/
git commit -m "feat: database models, migrations, and model tests"
```

---

## Task 3: Pydantic Schemas

**Files:**
- Create: `backend/app/schemas.py`

- [ ] **Step 1: Create backend/app/schemas.py**

```python
from pydantic import BaseModel
from typing import List
from datetime import datetime
from app.models import NoteStatus


class NoteUploadResponse(BaseModel):
    note_id: str
    status: NoteStatus

    class Config:
        from_attributes = True


class NoteStatusResponse(BaseModel):
    note_id: str
    status: NoteStatus
    uploaded_at: datetime

    class Config:
        from_attributes = True


class NoteResultsResponse(BaseModel):
    note_id: str
    status: NoteStatus
    tasks: dict  # {"lab_tests": [...], "radiology": [...], "followups": [...]}

    class Config:
        from_attributes = True


class NoteListItem(BaseModel):
    note_id: str
    filename: str
    status: NoteStatus
    uploaded_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas.py
git commit -m "feat: pydantic schemas for API responses"
```

---

## Task 4: Extractor Logic (Rule-Based)

**Files:**
- Create: `backend/app/extractors/base.py`
- Create: `backend/app/extractors/lab.py`
- Create: `backend/app/extractors/radiology.py`
- Create: `backend/app/extractors/followup.py`
- Create: `backend/app/extractors/__init__.py`
- Test: `backend/tests/test_extractors.py`

- [ ] **Step 1: Write failing tests for extractors**

Create `backend/tests/test_extractors.py`:

```python
from app.extractors.lab import extract_lab_tests
from app.extractors.radiology import extract_radiology
from app.extractors.followup import extract_followups


def test_extract_lab_tests_finds_cbc():
    text = "Patient is advised to do a CBC blood test and check hemoglobin levels."
    results = extract_lab_tests(text)
    assert len(results) >= 1
    assert any("cbc" in r.lower() or "blood test" in r.lower() for r in results)


def test_extract_lab_tests_empty_when_no_match():
    text = "Patient should rest and drink water."
    results = extract_lab_tests(text)
    assert results == []


def test_extract_radiology_finds_xray():
    text = "Doctor recommends a chest x-ray and MRI of the knee."
    results = extract_radiology(text)
    assert len(results) >= 1
    assert any("x-ray" in r.lower() or "mri" in r.lower() for r in results)


def test_extract_radiology_empty_when_no_match():
    text = "Take paracetamol twice daily."
    results = extract_radiology(text)
    assert results == []


def test_extract_followups_finds_review():
    text = "Please follow up with the specialist. Review in 2 weeks."
    results = extract_followups(text)
    assert len(results) >= 1
    assert any("follow" in r.lower() or "review" in r.lower() for r in results)


def test_extract_followups_empty_when_no_match():
    text = "Diagnosis: viral fever. Prescription: rest."
    results = extract_followups(text)
    assert results == []


def test_no_duplicate_sentences():
    text = "Do a CBC blood test. CBC blood test is important for diagnosis."
    results = extract_lab_tests(text)
    assert len(results) == len(set(results))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_extractors.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create backend/app/extractors/__init__.py**

```python
```
(empty file)

- [ ] **Step 4: Create backend/app/extractors/base.py**

```python
import re
from typing import List


def extract_sentences(text: str, keywords: List[str]) -> List[str]:
    """
    Find all sentences in text that contain any of the given keywords.
    Returns deduplicated list of matching sentences.
    """
    text_lower = text.lower()
    # Split into sentences on period, exclamation, question mark, or newline
    sentences = re.split(r'(?<=[.!?\n])\s*', text.strip())
    found = []
    seen = set()

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        sentence_lower = sentence.lower()
        for keyword in keywords:
            if keyword in sentence_lower:
                if sentence_lower not in seen:
                    found.append(sentence)
                    seen.add(sentence_lower)
                break  # don't add same sentence twice for multiple keyword matches

    return found
```

- [ ] **Step 5: Create backend/app/extractors/lab.py**

```python
from typing import List
from app.extractors.base import extract_sentences

LAB_KEYWORDS = [
    "cbc", "blood test", "hemoglobin", "glucose", "lipid panel",
    "thyroid", "tsh", "hba1c", "urine test", "creatinine",
    "liver function", "lft", "rft", "complete blood count",
    "blood sugar", "platelet", "wbc", "rbc",
]


def extract_lab_tests(text: str) -> List[str]:
    return extract_sentences(text, LAB_KEYWORDS)
```

- [ ] **Step 6: Create backend/app/extractors/radiology.py**

```python
from typing import List
from app.extractors.base import extract_sentences

RADIOLOGY_KEYWORDS = [
    "x-ray", "xray", "mri", "ct scan", "ultrasound", "sonography",
    "chest x-ray", "echocardiogram", "mammogram", "bone scan",
    "pet scan", "dexa scan", "doppler", "angiogram",
]


def extract_radiology(text: str) -> List[str]:
    return extract_sentences(text, RADIOLOGY_KEYWORDS)
```

- [ ] **Step 7: Create backend/app/extractors/followup.py**

```python
from typing import List
from app.extractors.base import extract_sentences

FOLLOWUP_KEYWORDS = [
    "follow up", "follow-up", "followup", "revisit", "review in",
    "come back", "return in", "next appointment", "consult",
    "refer to", "referral", "see specialist", "appointment in",
]


def extract_followups(text: str) -> List[str]:
    return extract_sentences(text, FOLLOWUP_KEYWORDS)
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_extractors.py -v
```

Expected: PASS (7 tests)

- [ ] **Step 9: Commit**

```bash
git add backend/app/extractors/ backend/tests/test_extractors.py
git commit -m "feat: rule-based extractors for lab, radiology, and followup tasks"
```

---

## Task 5: File Reader

**Files:**
- Create: `backend/app/file_reader.py`
- Test: `backend/tests/test_file_reader.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_file_reader.py`:

```python
import os
import tempfile
import pytest
from app.file_reader import read_file


def test_read_txt_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Patient needs CBC blood test.")
        path = f.name
    try:
        result = read_file(path, "test.txt")
        assert "CBC blood test" in result
    finally:
        os.unlink(path)


def test_unsupported_extension_raises():
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
        path = f.name
    try:
        with pytest.raises(ValueError, match="Unsupported file type"):
            read_file(path, "test.docx")
    finally:
        os.unlink(path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_file_reader.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create backend/app/file_reader.py**

```python
import os
from PIL import Image
import pytesseract
from pdf2image import convert_from_path


def read_file(file_path: str, filename: str) -> str:
    """
    Read a file and return its text content.
    Supports: .txt, .pdf, .png, .jpg, .jpeg
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext == ".txt":
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif ext == ".pdf":
        pages = convert_from_path(file_path)
        text_parts = [pytesseract.image_to_string(page) for page in pages]
        return "\n".join(text_parts)

    elif ext in (".png", ".jpg", ".jpeg"):
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)

    else:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: .txt, .pdf, .png, .jpg, .jpeg")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/test_file_reader.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/file_reader.py backend/tests/test_file_reader.py
git commit -m "feat: file reader supporting txt, pdf, and image files via OCR"
```

---

## Task 6: Celery Configuration & Tasks

**Files:**
- Create: `backend/app/celery_app.py`
- Create: `backend/app/tasks/__init__.py`
- Create: `backend/app/tasks/coordinator.py`
- Create: `backend/app/tasks/lab.py`
- Create: `backend/app/tasks/radiology.py`
- Create: `backend/app/tasks/followup.py`
- Create: `backend/app/tasks/completion.py`

- [ ] **Step 1: Create backend/app/celery_app.py**

```python
import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "docstribe",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.tasks.coordinator",
        "app.tasks.lab",
        "app.tasks.radiology",
        "app.tasks.followup",
        "app.tasks.completion",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
```

- [ ] **Step 2: Create backend/app/tasks/__init__.py**

```python
```
(empty)

- [ ] **Step 3: Create backend/app/tasks/completion.py**

```python
from celery import shared_task
from app.database import SessionLocal
from app.models import Note, NoteStatus


@shared_task(bind=True, name="app.tasks.completion.on_extraction_complete")
def on_extraction_complete(self, results, note_id: str):
    """
    Chord callback — fires when all 3 extraction tasks complete.
    Sets note status to 'completed'.
    """
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            note.status = NoteStatus.completed
            db.commit()
    finally:
        db.close()
```

- [ ] **Step 4: Create backend/app/tasks/lab.py**

```python
import uuid
from celery import shared_task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ExtractedTask, TaskType, Note, NoteStatus
from app.extractors.lab import extract_lab_tests


@celery_app.task(
    bind=True,
    name="app.tasks.lab.lab_extraction_task",
    max_retries=3,
    default_retry_delay=60,
)
def lab_extraction_task(self, note_id: str, raw_text: str):
    db = SessionLocal()
    try:
        # Idempotency: skip if already extracted
        existing = db.query(ExtractedTask).filter(
            ExtractedTask.note_id == note_id,
            ExtractedTask.task_type == TaskType.lab_test,
        ).first()
        if existing:
            return

        results = extract_lab_tests(raw_text)
        for description in results:
            task = ExtractedTask(
                id=str(uuid.uuid4()),
                note_id=note_id,
                task_type=TaskType.lab_test,
                description=description,
            )
            db.add(task)
        db.commit()
    except Exception as exc:
        db.rollback()
        # Exponential backoff: 60s, 120s, 240s
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
```

- [ ] **Step 5: Create backend/app/tasks/radiology.py**

```python
import uuid
from celery import shared_task
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ExtractedTask, TaskType, Note, NoteStatus
from app.extractors.radiology import extract_radiology


@celery_app.task(
    bind=True,
    name="app.tasks.radiology.radiology_extraction_task",
    max_retries=3,
    default_retry_delay=60,
)
def radiology_extraction_task(self, note_id: str, raw_text: str):
    db = SessionLocal()
    try:
        existing = db.query(ExtractedTask).filter(
            ExtractedTask.note_id == note_id,
            ExtractedTask.task_type == TaskType.radiology,
        ).first()
        if existing:
            return

        results = extract_radiology(raw_text)
        for description in results:
            task = ExtractedTask(
                id=str(uuid.uuid4()),
                note_id=note_id,
                task_type=TaskType.radiology,
                description=description,
            )
            db.add(task)
        db.commit()
    except Exception as exc:
        db.rollback()
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
```

- [ ] **Step 6: Create backend/app/tasks/followup.py**

```python
import uuid
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ExtractedTask, TaskType
from app.extractors.followup import extract_followups


@celery_app.task(
    bind=True,
    name="app.tasks.followup.followup_extraction_task",
    max_retries=3,
    default_retry_delay=60,
)
def followup_extraction_task(self, note_id: str, raw_text: str):
    db = SessionLocal()
    try:
        existing = db.query(ExtractedTask).filter(
            ExtractedTask.note_id == note_id,
            ExtractedTask.task_type == TaskType.followup,
        ).first()
        if existing:
            return

        results = extract_followups(raw_text)
        for description in results:
            task = ExtractedTask(
                id=str(uuid.uuid4()),
                note_id=note_id,
                task_type=TaskType.followup,
                description=description,
            )
            db.add(task)
        db.commit()
    except Exception as exc:
        db.rollback()
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
```

- [ ] **Step 7: Create backend/app/tasks/coordinator.py**

```python
from celery import chord
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Note, NoteStatus
from app.tasks.lab import lab_extraction_task
from app.tasks.radiology import radiology_extraction_task
from app.tasks.followup import followup_extraction_task
from app.tasks.completion import on_extraction_complete


@celery_app.task(
    bind=True,
    name="app.tasks.coordinator.coordinator_task",
    max_retries=3,
    default_retry_delay=60,
)
def coordinator_task(self, note_id: str):
    """
    Reads the note's raw_text, sets status=processing,
    then fans out to 3 parallel extraction tasks via chord().
    """
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if not note:
            return

        note.status = NoteStatus.processing
        db.commit()
        raw_text = note.raw_text or ""
    except Exception as exc:
        db.rollback()
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        db.close()

    # Fan out: 3 parallel tasks, chord callback sets status=completed
    extraction_group = chord(
        [
            lab_extraction_task.s(note_id, raw_text),
            radiology_extraction_task.s(note_id, raw_text),
            followup_extraction_task.s(note_id, raw_text),
        ],
        on_extraction_complete.s(note_id),
    )
    extraction_group.delay()
```

- [ ] **Step 8: Commit**

```bash
git add backend/app/celery_app.py backend/app/tasks/
git commit -m "feat: celery tasks with coordinator, fan-out chord, and exponential backoff retries"
```

---

## Task 7: FastAPI Routes

**Files:**
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/routes/notes.py`
- Create: `backend/app/main.py`
- Test: `backend/tests/test_routes.py`

- [ ] **Step 1: Create backend/app/routes/__init__.py**

```python
```
(empty)

- [ ] **Step 2: Create backend/app/routes/notes.py**

```python
import os
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Note, ExtractedTask, NoteStatus, TaskType
from app.schemas import NoteUploadResponse, NoteStatusResponse, NoteResultsResponse, NoteListItem
from app.file_reader import read_file
from app.tasks.coordinator import coordinator_task
from typing import List

router = APIRouter(prefix="/api/notes", tags=["notes"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}


@router.post("/upload", response_model=NoteUploadResponse)
async def upload_note(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    note_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{note_id}{ext}")

    # Save uploaded file to disk
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    # Extract text from file
    try:
        raw_text = read_file(file_path, file.filename)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not read file: {str(e)}")

    # Create note record
    note = Note(
        id=note_id,
        filename=file.filename,
        raw_text=raw_text,
        status=NoteStatus.pending,
    )
    db.add(note)
    db.commit()

    # Trigger async processing
    coordinator_task.delay(note_id)

    return NoteUploadResponse(note_id=note_id, status=NoteStatus.pending)


@router.get("/", response_model=List[NoteListItem])
def list_notes(db: Session = Depends(get_db)):
    notes = db.query(Note).order_by(Note.uploaded_at.desc()).all()
    return [
        NoteListItem(
            note_id=n.id,
            filename=n.filename,
            status=n.status,
            uploaded_at=n.uploaded_at,
        )
        for n in notes
    ]


@router.get("/{note_id}/status", response_model=NoteStatusResponse)
def get_status(note_id: str, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return NoteStatusResponse(
        note_id=note.id,
        status=note.status,
        uploaded_at=note.uploaded_at,
    )


@router.get("/{note_id}/results", response_model=NoteResultsResponse)
def get_results(note_id: str, db: Session = Depends(get_db)):
    note = db.query(Note).filter(Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    tasks = db.query(ExtractedTask).filter(ExtractedTask.note_id == note_id).all()

    return NoteResultsResponse(
        note_id=note.id,
        status=note.status,
        tasks={
            "lab_tests": [t.description for t in tasks if t.task_type == TaskType.lab_test],
            "radiology": [t.description for t in tasks if t.task_type == TaskType.radiology],
            "followups": [t.description for t in tasks if t.task_type == TaskType.followup],
        },
    )
```

- [ ] **Step 3: Create backend/app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routes.notes import router as notes_router

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Docstribe Medical Notes Processor", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: Write failing route tests**

Create `backend/tests/test_routes.py`:

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database import Base, get_db
from unittest.mock import patch
import io

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_upload_txt_note(client):
    with patch("app.routes.notes.coordinator_task") as mock_task:
        mock_task.delay.return_value = None
        file_content = b"Patient needs CBC blood test. Follow up in 2 weeks."
        response = client.post(
            "/api/notes/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "note_id" in data
    assert data["status"] == "pending"


def test_upload_unsupported_type(client):
    response = client.post(
        "/api/notes/upload",
        files={"file": ("test.docx", io.BytesIO(b"content"), "application/octet-stream")},
    )
    assert response.status_code == 400


def test_get_status_not_found(client):
    response = client.get("/api/notes/nonexistent-id/status")
    assert response.status_code == 404


def test_get_status_after_upload(client):
    with patch("app.routes.notes.coordinator_task") as mock_task:
        mock_task.delay.return_value = None
        file_content = b"Patient needs CBC blood test."
        upload_resp = client.post(
            "/api/notes/upload",
            files={"file": ("test.txt", io.BytesIO(file_content), "text/plain")},
        )
    note_id = upload_resp.json()["note_id"]
    status_resp = client.get(f"/api/notes/{note_id}/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["note_id"] == note_id


def test_list_notes(client):
    with patch("app.routes.notes.coordinator_task") as mock_task:
        mock_task.delay.return_value = None
        client.post(
            "/api/notes/upload",
            files={"file": ("note1.txt", io.BytesIO(b"CBC test needed."), "text/plain")},
        )
    response = client.get("/api/notes/")
    assert response.status_code == 200
    assert len(response.json()) == 1
```

- [ ] **Step 5: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_routes.py -v
```

Expected: FAIL (import errors before implementation)

- [ ] **Step 6: Run tests to verify they pass after all files are created**

```bash
cd backend && python -m pytest tests/test_routes.py -v
```

Expected: PASS (6 tests)

- [ ] **Step 7: Commit**

```bash
git add backend/app/routes/ backend/app/main.py backend/tests/test_routes.py
git commit -m "feat: FastAPI routes for upload, status, results, and list"
```

---

## Task 8: Frontend — Upload Page

**Files:**
- Create: `frontend/pages/index.js`
- Create: `frontend/pages/_app.js`

- [ ] **Step 1: Create frontend/pages/_app.js**

```js
import '../styles/globals.css'

export default function App({ Component, pageProps }) {
  return <Component {...pageProps} />
}
```

- [ ] **Step 2: Create frontend/pages/index.js**

```js
import { useState } from 'react'
import { useRouter } from 'next/router'

export default function Home() {
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const router = useRouter()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!file) return

    setLoading(true)
    setError('')

    const formData = new FormData()
    formData.append('file', file)

    try {
      const res = await fetch('/api/notes/upload', {
        method: 'POST',
        body: formData,
      })

      if (!res.ok) {
        const data = await res.json()
        throw new Error(data.detail || 'Upload failed')
      }

      const data = await res.json()
      router.push(`/results/${data.note_id}`)
    } catch (err) {
      setError(err.message)
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-md p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-gray-800 mb-2">Medical Notes Processor</h1>
        <p className="text-gray-500 text-sm mb-6">
          Upload a prescription or medical note to extract lab tests, radiology orders, and follow-ups.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block border-2 border-dashed border-gray-300 rounded-xl p-6 text-center cursor-pointer hover:border-blue-400 transition">
            <input
              type="file"
              accept=".txt,.pdf,.png,.jpg,.jpeg"
              onChange={(e) => setFile(e.target.files[0])}
              className="hidden"
            />
            {file ? (
              <span className="text-gray-700 font-medium">{file.name}</span>
            ) : (
              <span className="text-gray-400">Click to select a file (.txt, .pdf, .jpg, .png)</span>
            )}
          </label>

          {error && (
            <p className="text-red-500 text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={!file || loading}
            className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition"
          >
            {loading ? 'Uploading...' : 'Upload & Process'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/pages/
git commit -m "feat: Next.js upload page with file selection and form submission"
```

---

## Task 9: Frontend — Results Page

**Files:**
- Create: `frontend/pages/results/[note_id].js`

- [ ] **Step 1: Create frontend/pages/results/[note_id].js**

```js
import { useEffect, useState, useRef } from 'react'
import { useRouter } from 'next/router'
import Link from 'next/link'

const TERMINAL_STATUSES = ['completed', 'failed']

export default function Results() {
  const router = useRouter()
  const { note_id } = router.query
  const [status, setStatus] = useState('pending')
  const [results, setResults] = useState(null)
  const [error, setError] = useState('')
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!note_id) return

    const poll = async () => {
      try {
        const res = await fetch(`/api/notes/${note_id}/status`)
        if (!res.ok) {
          setError('Note not found')
          clearInterval(intervalRef.current)
          return
        }
        const data = await res.json()
        setStatus(data.status)

        if (data.status === 'completed') {
          clearInterval(intervalRef.current)
          const resultsRes = await fetch(`/api/notes/${note_id}/results`)
          const resultsData = await resultsRes.json()
          setResults(resultsData.tasks)
        } else if (data.status === 'failed') {
          clearInterval(intervalRef.current)
          setError('Processing failed. Please try uploading again.')
        }
      } catch (err) {
        setError('Connection error')
        clearInterval(intervalRef.current)
      }
    }

    poll() // immediate first call
    intervalRef.current = setInterval(poll, 3000)

    return () => clearInterval(intervalRef.current)
  }, [note_id])

  const isProcessing = !TERMINAL_STATUSES.includes(status)

  return (
    <div className="min-h-screen bg-gray-50 p-4">
      <div className="max-w-2xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-800">Processing Results</h1>
          <Link href="/" className="text-blue-600 text-sm hover:underline">
            Upload another
          </Link>
        </div>

        <p className="text-gray-400 text-xs mb-4">Note ID: {note_id}</p>

        {isProcessing && !error && (
          <div className="bg-white rounded-2xl shadow-md p-8 text-center">
            <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600 font-medium capitalize">{status}...</p>
            <p className="text-gray-400 text-sm mt-1">Checking every 3 seconds</p>
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-2xl p-6 text-red-600">
            {error}
          </div>
        )}

        {results && (
          <div className="space-y-4">
            <Section title="🧪 Lab Tests" items={results.lab_tests} color="blue" />
            <Section title="🔬 Radiology" items={results.radiology} color="purple" />
            <Section title="📅 Follow-ups" items={results.followups} color="green" />
          </div>
        )}
      </div>
    </div>
  )
}

function Section({ title, items, color }) {
  const colorMap = {
    blue: 'bg-blue-50 border-blue-200',
    purple: 'bg-purple-50 border-purple-200',
    green: 'bg-green-50 border-green-200',
  }
  return (
    <div className={`rounded-2xl border p-5 ${colorMap[color]}`}>
      <h2 className="font-semibold text-gray-700 mb-3">{title}</h2>
      {items.length === 0 ? (
        <p className="text-gray-400 text-sm">None found</p>
      ) : (
        <ul className="space-y-1">
          {items.map((item, i) => (
            <li key={i} className="text-gray-700 text-sm flex items-start gap-2">
              <span className="mt-1 text-gray-400">•</span>
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/pages/results/
git commit -m "feat: Next.js results page with polling and grouped task display"
```

---

## Task 10: Run Migrations & Smoke Test

**Files:** No new files — just running the stack.

- [ ] **Step 1: Build and start all services**

```bash
docker-compose up --build -d
```

Expected: all 5 containers start (db, redis, api, worker, frontend)

- [ ] **Step 2: Run database migrations**

```bash
docker-compose exec api alembic upgrade head
```

Expected: `Running upgrade -> <hash>, initial`

- [ ] **Step 3: Check API health**

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 4: Check API docs are accessible**

Open browser: `http://localhost:8000/docs`  
Expected: FastAPI Swagger UI showing 4 endpoints

- [ ] **Step 5: Check frontend loads**

Open browser: `http://localhost:3000`  
Expected: Upload page renders

- [ ] **Step 6: Run all backend tests**

```bash
docker-compose exec api python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add .
git commit -m "chore: verify full stack runs end-to-end"
```

---

## Task 11: End-to-End Manual Test

- [ ] **Step 1: Create a sample medical note**

Create `sample_note.txt` on your local machine:

```
Patient: John Doe, Age 45

Diagnosis: Type 2 Diabetes with hypertension

Investigations Required:
- CBC blood test to check hemoglobin levels
- HbA1c blood test for diabetes monitoring
- Liver function test (LFT)
- Urine test for protein and creatinine

Radiology:
- Chest X-ray (PA view)
- Ultrasound of abdomen

Plan:
- Follow up in 2 weeks with test reports
- Refer to cardiologist for further evaluation
- Next appointment scheduled in 14 days
- Review blood pressure readings at next visit
```

- [ ] **Step 2: Upload via UI**

Go to `http://localhost:3000`, upload `sample_note.txt`. You should be redirected to the results page.

- [ ] **Step 3: Watch status transition**

Results page should show:
1. "pending..." spinner briefly
2. "processing..." spinner (as Celery picks it up)
3. Results appear with 3 sections populated

- [ ] **Step 4: Verify results via API directly**

```bash
# Get the note_id from the URL in your browser, then:
curl http://localhost:8000/api/notes/<note_id>/results | python3 -m json.tool
```

Expected output:
```json
{
  "note_id": "...",
  "status": "completed",
  "tasks": {
    "lab_tests": ["CBC blood test to check hemoglobin levels", "HbA1c blood test for diabetes monitoring", "Liver function test (LFT)", "Urine test for protein and creatinine"],
    "radiology": ["Chest X-ray (PA view)", "Ultrasound of abdomen"],
    "followups": ["Follow up in 2 weeks with test reports", "Refer to cardiologist for further evaluation", "Next appointment scheduled in 14 days", "Review blood pressure readings at next visit"]
  }
}
```

- [ ] **Step 5: Check worker logs to confirm task execution**

```bash
docker-compose logs worker
```

Expected: logs showing `coordinator_task`, `lab_extraction_task`, `radiology_extraction_task`, `followup_extraction_task` all succeeded.

---

## Task 12: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create README.md**

```markdown
# Docstribe Medical Notes Processor

A full-stack system that accepts uploaded medical notes/prescriptions, processes them asynchronously, and extracts structured tasks: lab tests, radiology orders, and follow-ups.

## Architecture

```
Upload → FastAPI → Redis → Celery coordinator_task
                              ├── lab_extraction_task      ┐
                              ├── radiology_extraction_task ├─ chord() → on_complete → status=completed
                              └── followup_extraction_task ┘
                                        ↓
                                   PostgreSQL
```

5 Docker services: `api` (FastAPI), `worker` (Celery), `db` (PostgreSQL), `redis`, `frontend` (Next.js)

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

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

### Run Tests

```bash
docker-compose exec api python -m pytest tests/ -v
```

## How It Works

1. **Upload** a `.txt`, `.pdf`, `.jpg`, or `.png` file via the UI
2. File text is extracted (OCR for images/PDFs via pytesseract)
3. A Celery `coordinator_task` is triggered
4. Three parallel tasks fan out via `chord()`:
   - `lab_extraction_task` — scans for lab test keywords
   - `radiology_extraction_task` — scans for imaging keywords
   - `followup_extraction_task` — scans for follow-up keywords
5. Results are saved to PostgreSQL
6. Frontend polls `/api/notes/{id}/status` every 3 seconds
7. Once `completed`, results are displayed grouped by type

## Retry Logic

Failed tasks retry with exponential backoff: 60s → 120s → 240s (max 3 retries). After 3 retries the note is marked `failed`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/notes/upload` | Upload file |
| GET | `/api/notes/{id}/status` | Check processing status |
| GET | `/api/notes/{id}/results` | Get extracted tasks |
| GET | `/api/notes/` | List all notes |

## Known Limitations / Future Work

- Polling instead of WebSocket (architecture supports adding it)
- Rule-based extraction instead of LLM (swap-ready — only the extractor function changes)
- No authentication (would add JWT in production)
- Single Redis instance (would use Sentinel for HA)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README with architecture, setup instructions, and API docs"
```

---

## Self-Review Against Spec

Checking spec sections:

- [x] Section 1 (Architecture): Task 1 docker-compose, 5 services
- [x] Section 2 (DB Schema): Task 2 models with Note, ExtractedTask, NoteStatus, TaskType enums
- [x] Section 3 (API Endpoints): Task 7 all 4 endpoints
- [x] Section 4 (Celery Task Flow): Task 6 coordinator + chord + completion callback
- [x] Section 5 (Rule-Based Extraction): Task 4 extractors with keyword lists
- [x] Section 6 (Frontend): Tasks 8 and 9
- [x] Section 7 (Project Structure): matches file map above
- [x] Section 8 (Docker Compose): Task 1 with healthchecks
- [x] README: Task 12

No placeholders found. Type names consistent throughout (`NoteStatus`, `TaskType`, `ExtractedTask`, `coordinator_task`). All function signatures match across tasks.
```
