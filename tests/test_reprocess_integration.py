import pytest
from fastapi.testclient import TestClient
from main import app
from database import init_db, create_job
import json

client = TestClient(app)

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Initialize database"""
    init_db()

@pytest.mark.skip(reason="Requires implementation of Tasks 1-11: POST /api/reprocess and GET /api/reprocess-history endpoints")
def test_full_reprocess_flow(setup_db):
    """Test complete reprocess workflow"""
    # 1. Create job
    job_id = create_job(api_tier='free')
    assert job_id > 0

    # 2. Get failed files (should be empty initially)
    response = client.get(f"/api/failed-files/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data['total_failures'] == 0

    # 3. Try to reprocess empty (should fail or do nothing)
    response = client.post(f"/api/reprocess/{job_id}", json={"files": []})
    assert response.status_code == 400  # No files specified

    # 4. Get history (should be empty)
    response = client.get(f"/api/reprocess-history/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data['total_attempts'] == 0

@pytest.mark.skip(reason="Requires implementation of Tasks 1-11: POST /api/reprocess and GET /api/reprocess-history endpoints")
def test_reprocess_nonexistent_job(setup_db):
    """Test reprocess on non-existent job returns 404"""
    response = client.get("/api/failed-files/999999")
    assert response.status_code == 404

    response = client.post("/api/reprocess/999999", json={"files": []})
    assert response.status_code == 404

    response = client.get("/api/reprocess-history/999999")
    assert response.status_code == 404
