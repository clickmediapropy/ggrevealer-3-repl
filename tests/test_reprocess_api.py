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

def test_reprocess_failed_files_endpoint(setup_db):
    """Test POST /api/reprocess/{job_id} endpoint"""
    job_id = create_job(api_tier='free')

    request_data = {
        "files": [
            {"source": "pt4", "id": 1}
        ]
    }

    response = client.post(
        f"/api/reprocess/{job_id}",
        json=request_data
    )

    assert response.status_code in [200, 202]  # 200 or 202 Accepted
    data = response.json()
    assert 'reprocess_id' in data
    assert data['job_id'] == job_id
    assert data['status'] in ['started', 'pending']

def test_reprocess_invalid_job(setup_db):
    """Test endpoint returns 404 for non-existent job"""
    request_data = {"files": [{"source": "pt4", "id": 1}]}

    response = client.post(
        "/api/reprocess/999999",
        json=request_data
    )

    assert response.status_code == 404

def test_get_reprocess_history_endpoint(setup_db):
    """Test GET /api/reprocess-history/{job_id} endpoint"""
    job_id = create_job(api_tier='free')

    response = client.get(f"/api/reprocess-history/{job_id}")

    assert response.status_code == 200
    data = response.json()
    assert 'attempts' in data
    assert 'total_attempts' in data
    assert isinstance(data['attempts'], list)
