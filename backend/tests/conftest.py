"""Shared fixtures. Environment is pinned before the app imports its engine."""

import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["SEED_ON_STARTUP"] = "false"
os.environ["SIMULATOR_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient

from app.db import Base, SessionLocal, engine
from app.main import app
from app.services.seed import seed_catalog


@pytest.fixture
def db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    seed_catalog(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    with TestClient(app) as test_client:
        yield test_client
