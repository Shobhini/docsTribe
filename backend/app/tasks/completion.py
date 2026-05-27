import logging
from datetime import datetime
from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Note, NoteStatus

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.tasks.completion.on_extraction_complete")
def on_extraction_complete(self, results, note_id: str):
    """
    Chord callback — fires when all 3 extraction tasks complete successfully.
    Sets note status to 'completed' and records completed_at timestamp.
    """
    db = SessionLocal()
    try:
        note = db.query(Note).filter(Note.id == note_id).first()
        if note:
            note.status = NoteStatus.completed
            note.completed_at = datetime.utcnow()
            db.commit()
            duration = None
            if note.processing_started_at:
                duration = (note.completed_at - note.processing_started_at).total_seconds()
            logger.info("on_extraction_complete note_id=%s duration=%.2fs", note_id, duration or 0)
    finally:
        db.close()
