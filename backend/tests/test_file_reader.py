import os
import tempfile
import pytest
from app.file_reader import read_file


def test_read_txt_file():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Patient needs CBC blood test.")
        path = f.name
    try:
        result = read_file(path, "test.txt")
        assert "CBC blood test" in result
    finally:
        os.unlink(path)


def test_unsupported_extension_raises():
    with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
        path = f.name
    try:
        with pytest.raises(ValueError, match="Unsupported file type"):
            read_file(path, "test.docx")
    finally:
        os.unlink(path)
