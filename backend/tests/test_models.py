# ============================================================
# test_models.py
# ------------------------------------------------------------
# This file contains TESTS for the database models we defined
# in app/models.py.
#
# We use 'pytest' — the most popular Python testing framework.
# pytest looks for functions whose names start with 'test_'
# and runs them automatically when you run:
#   python -m pytest tests/test_models.py -v
#
# IMPORTANT: We do NOT use the real PostgreSQL database for
# tests. Instead we use SQLite in-memory mode:
#   - SQLite is a lightweight database that comes built into Python
#   - "in-memory" means it exists only in RAM while tests run,
#     and is destroyed afterwards — no files left behind
#   - This makes tests fast, isolated, and independent of any
#     running database server
# ============================================================


# -- IMPORTS --------------------------------------------------

# pytest is the testing framework that discovers and runs our tests.
# We also use it to define 'fixtures' (reusable setup code).
import pytest

# We import SQLAlchemy tools to set up a test database.
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base from our database.py — it holds the table definitions
# (metadata) that we need to create the tables in the test DB.
from app.database import Base

# Import the model classes and enums we want to test.
from app.models import Note, ExtractedTask, NoteStatus, TaskType

# uuid is used to generate unique IDs for test records.
import uuid


# -- TEST DATABASE URL ----------------------------------------

# This is the connection string for the in-memory SQLite database.
#
# "sqlite:///:memory:" means:
#   sqlite:// -> use SQLite (not PostgreSQL)
#   :memory:  -> store everything in RAM, not a file on disk
#
# Each test run starts with a fresh empty database — no leftover
# data from previous tests.
TEST_DB_URL = "sqlite:///:memory:"


# -- FIXTURE --------------------------------------------------

# A 'fixture' in pytest is a reusable setup/teardown function.
# The @pytest.fixture decorator tells pytest that 'db' is a fixture.
#
# When a test function has a parameter named 'db', pytest
# automatically calls this fixture and injects the result.
#
# What this fixture does:
#   1. Creates a SQLite in-memory engine
#   2. Creates all tables (notes, extracted_tasks) in that engine
#   3. Opens a database session
#   4. Yields (gives) the session to the test
#   5. After the test finishes, closes the session
#   6. Drops (deletes) all tables to clean up
@pytest.fixture
def db():
    # Create the in-memory SQLite engine.
    # connect_args={"check_same_thread": False} is a SQLite-specific
    # setting that allows the connection to be used across threads.
    # (SQLAlchemy requires this for SQLite.)
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

    # Base.metadata.create_all(engine) reads all the model classes
    # that inherit from Base (Note and ExtractedTask) and creates
    # their corresponding tables in the test database.
    Base.metadata.create_all(engine)

    # Create a session factory bound to our test engine.
    Session = sessionmaker(bind=engine)

    # Open an actual session (our workspace to interact with the DB).
    session = Session()

    # 'yield' pauses this function and gives 'session' to the test.
    # Everything AFTER yield runs when the test is done.
    yield session

    # Cleanup: close the session and drop all tables.
    # This runs even if the test fails — like a 'finally' block.
    session.close()
    Base.metadata.drop_all(engine)


# -- TEST 1: Create a Note ------------------------------------

# Test functions must start with 'test_' for pytest to find them.
# The parameter 'db' matches our fixture above — pytest injects
# the session automatically.
def test_create_note(db):
    # Create a new Note object (does NOT save to DB yet).
    # This is just a Python object in memory at this point.
    note = Note(
        id=str(uuid.uuid4()),              # generate a random unique ID
        filename="test.txt",               # name of the uploaded file
        raw_text="Patient needs CBC blood test.",  # content of the note
        status=NoteStatus.pending,         # starts as 'pending'
    )

    # db.add(note) -> tells SQLAlchemy to track this object.
    # Still not saved to the database yet.
    db.add(note)

    # db.commit() -> actually writes the data to the database.
    # This is like pressing "Save" in a word document.
    # After commit, the note is permanently stored (in our test DB).
    db.commit()

    # db.query(Note).first() -> fetch the first row from the notes table.
    # This is equivalent to SQL: SELECT * FROM notes LIMIT 1;
    saved = db.query(Note).first()

    # assert statements CHECK that values are what we expect.
    # If an assert fails, pytest marks the test as FAILED and shows
    # what the actual vs expected values were.
    #
    # Here we verify the data was actually saved correctly.
    assert saved.filename == "test.txt"         # filename should match
    assert saved.status == NoteStatus.pending   # status should be pending


# -- TEST 2: Create an ExtractedTask linked to a Note ---------

def test_create_extracted_task(db):
    # First create and save a Note — we need it before we can
    # create a task, because the task must reference a valid note.
    note = Note(
        id=str(uuid.uuid4()),
        filename="test.txt",
        raw_text="Patient needs CBC blood test.",
        status=NoteStatus.pending,
    )
    db.add(note)
    db.commit()

    # Now create an ExtractedTask linked to the note above.
    # note_id=note.id creates the foreign key link between the
    # extracted_tasks table and the notes table.
    task = ExtractedTask(
        id=str(uuid.uuid4()),
        note_id=note.id,                   # link to the parent note
        task_type=TaskType.lab_test,        # type of medical task
        description="CBC blood test",       # what the task is
    )
    db.add(task)
    db.commit()

    # Fetch the saved task from the database.
    # SELECT * FROM extracted_tasks LIMIT 1;
    saved = db.query(ExtractedTask).first()

    # Verify the task was saved with the correct values.
    assert saved.description == "CBC blood test"   # description matches
    assert saved.task_type == TaskType.lab_test     # type is lab_test


def test_relationship_navigation(db):
    # Verify that note.tasks and task.note ORM relationships work correctly.
    note = Note(
        id=str(uuid.uuid4()),
        filename="test.txt",
        raw_text="CBC blood test needed.",
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
    db.refresh(note)

    # Navigate parent -> children
    assert len(note.tasks) == 1
    assert note.tasks[0].description == "CBC blood test"

    # Navigate child -> parent
    assert task.note.filename == "test.txt"


def test_cascade_delete(db):
    # Verify that deleting a Note also deletes its ExtractedTask children.
    note = Note(
        id=str(uuid.uuid4()),
        filename="cascade_test.txt",
        raw_text="Follow up in 2 weeks.",
        status=NoteStatus.pending,
    )
    db.add(note)
    db.commit()

    task = ExtractedTask(
        id=str(uuid.uuid4()),
        note_id=note.id,
        task_type=TaskType.followup,
        description="Follow up in 2 weeks",
    )
    db.add(task)
    db.commit()

    # Delete the parent note
    db.delete(note)
    db.commit()

    # Child task should be gone too (cascade delete)
    remaining = db.query(ExtractedTask).all()
    assert remaining == []
