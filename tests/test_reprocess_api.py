import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db, create_job
import json

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Initialize database once per session"""
    init_db()

def test_get_failed_files_endpoint():
    """Test GET /api/failed-files/{job_id} endpoint"""
    job_id = create_job(api_tier='free')

    response = client.get(f"/api/failed-files/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert 'pt4_failures' in data
    assert 'app_failures' in data
    assert 'total_failures' in data

def test_get_failed_files_job_not_found():
    """Test endpoint returns 404 for non-existent job"""
    response = client.get("/api/failed-files/999999")

    assert response.status_code == 404
