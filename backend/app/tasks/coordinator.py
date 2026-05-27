import logging
from datetime import datetime
from celery import chord
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Note, NoteStatus
from app.tasks.lab import lab_extraction_task
from app.tasks.radiology import radiology_extraction_task
from app.tasks.followup import followup_extraction_task
from app.tasks.completion import on_extraction_complete

logger = logging.getLogger(__name__)


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
        note.processing_started_at = datetime.utcnow()
        db.commit()
        raw_text = note.raw_text or ""
        logger.info("coordinator_task started note_id=%s", note_id)
    except Exception as exc:
        db.rollback()
        logger.exception("coordinator_task DB error note_id=%s retry=%d", note_id, self.request.retries)
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
        logger.info("coordinator_task dispatched chord note_id=%s", note_id)
    except Exception as exc:
        logger.exception("coordinator_task chord dispatch failed note_id=%s", note_id)
        fail_db = SessionLocal()
        try:
            note = fail_db.query(Note).filter(Note.id == note_id).first()
            if note:
                note.status = NoteStatus.failed
                note.failed_at = datetime.utcnow()
                fail_db.commit()
        finally:
            fail_db.close()
        raise
