import uuid
from celery.exceptions import MaxRetriesExceededError
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ExtractedTask, TaskType
from app.extractors.lab import extract_lab_tests


@celery_app.task(
    bind=True,
    name="app.tasks.lab.lab_extraction_task",
    max_retries=3,
)
def lab_extraction_task(self, note_id: str, raw_text: str):
    db = SessionLocal()
    try:
        # Idempotency: skip if already extracted for this note
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
    except MaxRetriesExceededError:
        fail_db = SessionLocal()
        try:
            from app.models import Note, NoteStatus
            note = fail_db.query(Note).filter(Note.id == note_id).first()
            if note:
                note.status = NoteStatus.failed
                fail_db.commit()
        finally:
            fail_db.close()
    except Exception as exc:
        db.rollback()
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
