from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Note, NoteStatus


@celery_app.task(bind=True, name="app.tasks.completion.on_extraction_complete")
def on_extraction_complete(self, results, note_id: str):
    """
    Chord callback — fires when all 3 extraction tasks complete successfully.
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
