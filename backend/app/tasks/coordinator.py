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
)
def coordinator_task(self, note_id: str):
    """
    Reads the note's raw_text, sets status=processing,
    then fans out to 3 parallel extraction tasks via chord().
    The chord callback sets status=completed when all 3 finish.
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

    try:
        extraction_group = chord(
            [
                lab_extraction_task.s(note_id, raw_text),
                radiology_extraction_task.s(note_id, raw_text),
                followup_extraction_task.s(note_id, raw_text),
            ],
            on_extraction_complete.s(note_id),
        )
        extraction_group.delay()
    except Exception as exc:
        fail_db = SessionLocal()
        try:
            note = fail_db.query(Note).filter(Note.id == note_id).first()
            if note:
                note.status = NoteStatus.failed
                fail_db.commit()
        finally:
            fail_db.close()
        raise
