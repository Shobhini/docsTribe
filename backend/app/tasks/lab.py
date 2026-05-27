import uuid
import logging
from celery.exceptions import MaxRetriesExceededError
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import ExtractedTask, TaskType
from app.extractors.lab import extract_lab_tests

logger = logging.getLogger(__name__)


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
            logger.info("lab_extraction_task already done, skipping note_id=%s", note_id)
            return

        logger.info("lab_extraction_task starting note_id=%s", note_id)
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
        logger.info("lab_extraction_task completed note_id=%s found=%d", note_id, len(results))
    except MaxRetriesExceededError:
        logger.error("lab_extraction_task max retries exceeded note_id=%s", note_id)
        fail_db = SessionLocal()
        try:
            from app.models import Note, NoteStatus
            from datetime import datetime
            note = fail_db.query(Note).filter(Note.id == note_id).first()
            if note:
                note.status = NoteStatus.failed
                note.failed_at = datetime.utcnow()
                fail_db.commit()
        finally:
            fail_db.close()
    except Exception as exc:
        db.rollback()
        countdown = 60 * (2 ** self.request.retries)
        logger.warning("lab_extraction_task failed note_id=%s retry=%d countdown=%ds", note_id, self.request.retries, countdown)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()
