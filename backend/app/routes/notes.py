import os
import uuid
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import Note, ExtractedTask, NoteStatus, TaskType
from app.schemas import NoteUploadResponse, NoteStatusResponse, NoteResultsResponse, NoteListItem
from app.file_reader import read_file
from app.tasks.coordinator import coordinator_task

router = APIRouter(prefix="/api/notes", tags=["notes"])

# Absolute path so uploads land in the same place regardless of cwd
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}


@router.post("/upload", response_model=NoteUploadResponse)
async def upload_note(file: UploadFile = File(...), db: Session = Depends(get_db)):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    note_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{note_id}{ext}")

    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)

    try:
        raw_text = read_file(file_path, file.filename)
    except Exception as e:
        os.remove(file_path)
        raise HTTPException(status_code=422, detail=f"Could not read file: {str(e)}")

    try:
        note = Note(
            id=note_id,
            filename=file.filename,
            raw_text=raw_text,
            status=NoteStatus.pending,
        )
        db.add(note)
        db.commit()
    except Exception:
        os.remove(file_path)
        raise

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
