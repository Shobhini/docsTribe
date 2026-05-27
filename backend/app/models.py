# ============================================================
# models.py
# ------------------------------------------------------------
# This file defines the DATABASE TABLES as Python classes.
#
# In SQLAlchemy, each Python class = one database table.
# Each class attribute (variable) = one column in that table.
#
# This style of working is called ORM (Object Relational
# Mapping) — it maps Python objects to database rows so you
# never have to write raw SQL like:
#   INSERT INTO notes (id, filename) VALUES (...)
# Instead you just do:
#   db.add(Note(filename="test.txt"))
# ============================================================


# -- IMPORTS --------------------------------------------------

# 'uuid' is a built-in Python module for generating unique IDs.
# UUID stands for Universally Unique Identifier.
# Example output: "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
# We use these as primary keys so every row has a unique ID.
import uuid

# 'datetime' lets us work with dates and times in Python.
# We use it to automatically record WHEN a note was created
# or last updated.
from datetime import datetime

# These are SQLAlchemy column types. Each one maps to a
# database column type:
#
#   Column    -> defines a column in a table
#   String    -> stores short text (like a filename)
#   Text      -> stores long text (like a full medical note)
#   Enum      -> stores one value from a fixed list of choices
#   DateTime  -> stores a date and time value
#   ForeignKey-> links a column to another table's column
from sqlalchemy import Column, String, Text, Enum, DateTime, ForeignKey, UniqueConstraint

# 'relationship' tells SQLAlchemy that two tables are
# connected, so you can access related rows easily.
# For example: note.tasks gives you all tasks for that note.
from sqlalchemy.orm import relationship

# Python's built-in 'enum' module lets us define a fixed
# set of allowed values — like a dropdown with set options.
import enum

# Import the Base class we created in database.py.
# Our models inherit from this so SQLAlchemy recognizes them
# as database tables.
from app.database import Base


# -- ENUMS ----------------------------------------------------
# An Enum defines a set of named constants.
# By inheriting from both 'str' and 'enum.Enum', each value
# is also a plain string — this works better with databases
# and JSON serialization.

# NoteStatus tracks where a medical note is in its lifecycle:
#
#   pending    -> uploaded but not yet processed
#   processing -> currently being analyzed
#   completed  -> analysis finished successfully
#   failed     -> something went wrong during processing
class NoteStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


# TaskType categorizes what kind of medical action was found
# in the note:
#
#   lab_test   -> e.g. "Order a blood test"
#   radiology  -> e.g. "Schedule an X-ray"
#   followup   -> e.g. "Patient should return in 2 weeks"
class TaskType(str, enum.Enum):
    lab_test = "lab_test"
    radiology = "radiology"
    followup = "followup"


# -- NOTE TABLE -----------------------------------------------

# The 'Note' class represents the 'notes' table in the DB.
# Each Note is one uploaded medical document.
#
# class Note(Base) means Note inherits from Base, which tells
# SQLAlchemy "this class is a database table".
class Note(Base):

    # __tablename__ is a special variable SQLAlchemy looks for.
    # It sets the actual name of the table in the database.
    __tablename__ = "notes"

    # -- COLUMNS --

    # id: the primary key — a unique identifier for each note.
    #
    # Column(String, ...)  -> data type is String (text)
    # primary_key=True     -> this column uniquely identifies each row
    # default=lambda: str(uuid.uuid4())
    #   -> when a new Note is created WITHOUT providing an id,
    #      Python automatically generates a unique UUID string.
    #   -> 'lambda' is an anonymous (unnamed) function. This is
    #      equivalent to:
    #         def generate_id():
    #             return str(uuid.uuid4())
    #      We use lambda here for brevity.
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # filename: the name of the uploaded file, e.g. "note_001.txt"
    # nullable=False means this column CANNOT be empty/None.
    # Every note MUST have a filename.
    filename = Column(String, nullable=False)

    # raw_text: the actual text content extracted from the file.
    # Text type is used for potentially very long strings.
    # nullable=True means it CAN be None (empty at first, filled later).
    raw_text = Column(Text, nullable=True)

    # status: current processing state of the note.
    # Enum(NoteStatus) tells the DB to only allow values defined
    # in our NoteStatus enum above.
    # default=NoteStatus.pending means every new note starts as "pending".
    status = Column(Enum(NoteStatus), default=NoteStatus.pending, nullable=False)

    # uploaded_at: timestamp of when the note was first created.
    # default=datetime.utcnow means it is automatically set to
    # the current UTC time when the row is first inserted.
    # NOTE: we pass 'datetime.utcnow' without () — this passes
    # the FUNCTION itself, not its result. SQLAlchemy calls it
    # each time a new row is created.
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # updated_at: timestamp of the last update to this note.
    # onupdate=datetime.utcnow automatically updates this column
    # to the current time whenever the row is modified.
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # processing_started_at: set when coordinator_task picks up the note.
    # Lets you measure queue wait time: processing_started_at - uploaded_at.
    processing_started_at = Column(DateTime, nullable=True)

    # completed_at / failed_at: terminal state timestamps.
    # Together with processing_started_at you can calculate extraction latency.
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)

    # celery_task_id: the ID Celery assigns to the coordinator_task.
    # Store it so you can look up the task in Flower or via Celery's inspect API
    # to trace exactly what happened to a note in the worker.
    celery_task_id = Column(String, nullable=True)

    # -- RELATIONSHIP --

    # 'tasks' is not a real column in the database.
    # It is a SQLAlchemy "relationship" — a shortcut that lets
    # you access all ExtractedTask rows linked to this Note.
    #
    # back_populates="note" -> on the ExtractedTask side, there
    #   is also a relationship called 'note' that points back here.
    #   This creates a two-way link between the two models.
    #
    # cascade="all, delete-orphan" -> if a Note is deleted,
    #   all its associated ExtractedTask rows are also deleted
    #   automatically. No orphan tasks left behind.
    #
    # Usage example:
    #   note = db.query(Note).first()
    #   print(note.tasks)  # -> list of ExtractedTask objects
    tasks = relationship(
        "ExtractedTask",
        back_populates="note",
        cascade="all, delete-orphan"
    )


# -- EXTRACTED TASK TABLE -------------------------------------

# The 'ExtractedTask' class represents the 'extracted_tasks' table.
# Each row is one medical action item extracted from a Note.
# For example, one note might produce 3 tasks:
#   - "Order CBC blood test"    (lab_test)
#   - "Schedule chest X-ray"   (radiology)
#   - "Follow up in 2 weeks"   (followup)
class ExtractedTask(Base):

    __tablename__ = "extracted_tasks"

    # id: unique identifier for each task (same UUID approach as Note)
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # note_id: this is a FOREIGN KEY — it stores the 'id' of the
    # Note this task belongs to. This is how we link the two tables.
    #
    # ForeignKey("notes.id") means:
    #   -> this value must match an existing 'id' in the 'notes' table
    #   -> it is a reference, not a copy — just the ID string
    # nullable=False -> every task MUST belong to a note
    note_id = Column(String, ForeignKey("notes.id"), nullable=False)

    # task_type: what kind of task this is (lab_test, radiology, followup)
    # Uses our TaskType enum so only valid values are accepted.
    task_type = Column(Enum(TaskType), nullable=False)

    # description: the actual text of the extracted task.
    # E.g. "Patient requires complete blood count (CBC) test."
    description = Column(Text, nullable=False)

    # created_at: when this task record was created.
    created_at = Column(DateTime, default=datetime.utcnow)

    # DB-level unique constraint: even if app-level idempotency check is bypassed
    # (e.g. two workers race), the database will reject duplicate rows.
    # This is a defense-in-depth pattern: app logic first, DB constraint as backstop.
    __table_args__ = (
        UniqueConstraint("note_id", "task_type", "description", name="uq_task_per_note"),
    )

    # -- RELATIONSHIP --

    # 'note' lets us easily navigate from a task back to its
    # parent Note object.
    #
    # back_populates="tasks" links this to the 'tasks' relationship
    # on the Note model, creating a two-way connection.
    #
    # Usage example:
    #   task = db.query(ExtractedTask).first()
    #   print(task.note.filename)  # -> filename of the parent note
    note = relationship("Note", back_populates="tasks")
