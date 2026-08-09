import os
os.environ["APP_ENV"] = "test"
os.environ["AUTONOMOUS_ENABLED"] = "False"

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    """
    Fixture that provides a TestClient for the FastAPI app.
    """
    with TestClient(app) as c:
        yield c
