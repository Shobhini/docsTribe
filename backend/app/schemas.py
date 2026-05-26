from pydantic import BaseModel
from typing import List, Dict
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
    tasks: Dict[str, List[str]]

    class Config:
        from_attributes = True


class NoteListItem(BaseModel):
    note_id: str
    filename: str
    status: NoteStatus
    uploaded_at: datetime

    class Config:
        from_attributes = True
