"""Integration tests for batch upload system"""

import os
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from io import BytesIO

from main import app
from database import init_db

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup test database before each test"""
    # Use test database
    os.environ['DATABASE_PATH'] = ':memory:'
    init_db()
    yield
    # Cleanup happens automatically with in-memory DB

def create_mock_file(filename: str, size_mb: int = 1):
    """Create a mock file for testing"""
    content = b'x' * (size_mb * 1024 * 1024)
    return (filename, BytesIO(content), 'text/plain')

def test_init_upload_job():
    """Test job initialization endpoint"""
    response = client.post("/api/upload/init", data={"api_tier": "free"})

    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "initialized"
    assert data["job_id"] > 0

def test_batch_upload_single_batch():
    """Test uploading a single batch of files"""
    # Initialize job
    init_response = client.post("/api/upload/init", data={"api_tier": "free"})
    job_id = init_response.json()["job_id"]

    # Upload batch
    response = client.post(f"/api/upload/batch/{job_id}", files={
        "txt_files": create_mock_file("test1.txt", 1),
        "screenshots": create_mock_file("screenshot1.png", 1)
    })

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == job_id
    assert data["batch_txt_count"] == 1
    assert data["batch_screenshot_count"] == 1
    assert data["total_txt_count"] == 1
    assert data["total_screenshot_count"] == 1

def test_batch_upload_multiple_batches():
    """Test uploading multiple batches sequentially"""
    # Initialize job
    init_response = client.post("/api/upload/init", data={"api_tier": "free"})
    job_id = init_response.json()["job_id"]

    # Upload batch 1
    response1 = client.post(f"/api/upload/batch/{job_id}", files={
        "txt_files": create_mock_file("test1.txt", 1)
    })
    assert response1.status_code == 200
    data1 = response1.json()
    assert data1["total_txt_count"] == 1

    # Upload batch 2
    response2 = client.post(f"/api/upload/batch/{job_id}", files={
        "txt_files": create_mock_file("test2.txt", 1),
        "screenshots": create_mock_file("screenshot1.png", 1)
    })
    assert response2.status_code == 200
    data2 = response2.json()
    assert data2["total_txt_count"] == 2
    assert data2["total_screenshot_count"] == 1

def test_batch_upload_invalid_job():
    """Test uploading to non-existent job returns 404"""
    response = client.post("/api/upload/batch/99999", files={
        "txt_files": create_mock_file("test1.txt", 1)
    })
    assert response.status_code == 404
    assert "Job no encontrado" in response.json()["detail"]

def test_batch_upload_exceeds_file_limit():
    """Test that exceeding file limits returns error"""
    from database import add_file
    from main import MAX_TXT_FILES

    # Initialize job
    init_response = client.post("/api/upload/init", data={"api_tier": "free"})
    job_id = init_response.json()["job_id"]

    # Manually add 300 files to reach the limit
    for i in range(MAX_TXT_FILES):
        add_file(job_id, f"test{i}.txt", "txt", f"/fake/path/test{i}.txt")

    # Try to upload 1 more file (should exceed limit)
    response = client.post(f"/api/upload/batch/{job_id}", files={
        "txt_files": create_mock_file("test_overflow.txt", 1)
    })

    assert response.status_code == 400
    assert "Excede el límite" in response.json()["detail"]
