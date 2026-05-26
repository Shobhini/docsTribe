# ============================================================
# database.py
# ------------------------------------------------------------
# This file is responsible for setting up the DATABASE
# CONNECTION for our application.
#
# Think of this file as the "bridge" between our Python code
# and the actual PostgreSQL database running somewhere.
# ============================================================


# -- IMPORTS --------------------------------------------------

# 'os' is a built-in Python module that lets us read
# environment variables (settings stored outside the code).
# Example: os.environ.get("MY_VAR") reads a variable called
# MY_VAR that was set in the terminal or a .env file.
import os

# SQLAlchemy is a popular Python library for talking to
# databases without writing raw SQL. Instead you write
# Python objects and SQLAlchemy converts them to SQL.
#
# 'create_engine' creates the actual connection to the DB.
# Think of it like opening a phone line to the database.
from sqlalchemy import create_engine

# 'declarative_base' gives us a base class that all our
# database models (tables) will inherit from.
# It keeps track of all tables we define.
from sqlalchemy.orm import declarative_base

# 'sessionmaker' creates a factory (a blueprint) for making
# database sessions. A session is like a temporary workspace
# where you can make changes before saving them to the DB.
from sqlalchemy.orm import sessionmaker


# -- DATABASE URL ---------------------------------------------

# The DATABASE_URL tells SQLAlchemy HOW and WHERE to connect
# to the database. It follows this format:
#
#   dialect://username:password@host:port/database_name
#
# os.environ.get("DATABASE_URL", "...default...")
#   - First it looks for an environment variable called DATABASE_URL
#   - If not found, it falls back to the default string shown below
#   - This is useful: in production we set the real URL as an
#     environment variable; in local dev we use the default
#
# Breaking down the default URL:
#   postgresql  -> use PostgreSQL database
#   postgres    -> username
#   postgres    -> password
#   localhost   -> the database is on the same machine
#   5432        -> default port PostgreSQL listens on
#   docstribe   -> name of the database
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/docstribe"
)


# -- ENGINE ---------------------------------------------------

# create_engine() sets up the connection pool to the database.
# It does NOT immediately open a connection — it just prepares
# everything so connections can be made when needed.
#
# Think of 'engine' as the driver that knows how to talk to
# the specific type of database (PostgreSQL in our case).
#
# connect_args is used here to pass extra options to SQLite
# when running tests. For PostgreSQL it has no effect and is
# safely ignored. The check_same_thread=False is required by
# SQLite when used with SQLAlchemy in pytest.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


# -- SESSION FACTORY ------------------------------------------

# sessionmaker() returns a class (a blueprint) for creating
# database sessions.
#
# autocommit=False  -> changes are NOT saved automatically;
#                      you must call db.commit() explicitly.
#                      This gives you control and safety.
#
# autoflush=False   -> SQLAlchemy won't automatically send
#                      pending changes to the DB before a query.
#                      Again, gives us more control.
#
# bind=engine       -> tells sessions to use our engine above
#                      (i.e., which database to talk to)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# -- BASE CLASS -----------------------------------------------

# declarative_base() returns a base class called 'Base'.
# Every table/model we create in models.py will inherit from
# this Base class. That is how SQLAlchemy knows which classes
# represent database tables.
#
# Example in models.py:
#   class Note(Base):   <-- inherits from this Base
#       __tablename__ = "notes"
Base = declarative_base()


# -- DEPENDENCY FUNCTION --------------------------------------

# get_db() is a "dependency" function used by FastAPI.
#
# FastAPI calls this function automatically whenever a route
# needs a database session. It:
#   1. Creates a new session (db = SessionLocal())
#   2. Hands it to the route function via 'yield'
#   3. Closes the session when the route is done
#
# 'yield' makes this a GENERATOR function. The code before
# yield runs at the start, and the code after (in finally)
# runs at the end — even if an error occurred.
#
# 'try / finally' ensures the session is ALWAYS closed,
# preventing memory leaks or locked database connections.
#
# Usage in a FastAPI route:
#   from fastapi import Depends
#   def my_route(db: Session = Depends(get_db)):
#       ...use db here...
def get_db():
    db = SessionLocal()   # open a new session
    try:
        yield db          # give the session to whoever asked for it
    finally:
        db.close()        # always close it when done, no matter what
