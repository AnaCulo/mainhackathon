import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

from .doubles import BACKEND, Double


@pytest.fixture
def setup(tmp_path):
    double = Double(tmp_path)
    app = create_app(double.settings, httpx.MockTransport(double))
    with TestClient(app) as client:
        yield client, double, app.state.db


@pytest.fixture
def submit(setup):
    client, _, _ = setup
    return lambda text, **kwargs: client.post(
        "/reports", json={"text": text, **kwargs}, headers=BACKEND
    )
