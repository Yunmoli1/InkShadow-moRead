"""Pytest fixtures: isolated data dir + TestClient."""
import os
import sys
import tempfile
from pathlib import Path

# Must set data dir BEFORE importing app modules
_tmp = tempfile.mkdtemp(prefix="moread-test-")
os.environ["MOREAD_DATA_DIR"] = _tmp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
