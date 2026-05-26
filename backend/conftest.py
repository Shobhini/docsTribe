# ============================================================
# conftest.py  (lives in the backend/ root)
# ------------------------------------------------------------
# pytest automatically loads this file BEFORE running any test.
# It is a special pytest configuration file — you don't import
# it yourself, pytest discovers and runs it on its own.
#
# PURPOSE HERE:
# Our app/database.py tries to connect to PostgreSQL the moment
# it is imported. In a test environment we have no PostgreSQL
# server running, so we redirect the DATABASE_URL to an
# in-memory SQLite database BEFORE any test file is imported.
#
# 'os.environ' is a dictionary-like object that holds all
# environment variables for the current process. Setting a
# value here is like doing `export DATABASE_URL=...` in the
# terminal, but only for this Python process.
# ============================================================

import os

# Set DATABASE_URL to SQLite in-memory BEFORE any app code loads.
# This ensures app/database.py uses SQLite instead of PostgreSQL.
# "sqlite:///:memory:" = a temporary database stored in RAM only.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
