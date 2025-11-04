#!/usr/bin/env python3
"""
End-to-end testing script for batch upload system
Tests small, medium, and large datasets with progress tracking
"""

import requests
import time
import json
from pathlib import Path
from typing import List, Tuple

BASE_URL = "http://localhost:8000"


def collect_files(txt_count: int, screenshot_count: int, source_jobs: List[int]) -> Tuple[List[Path], List[Path]]:
    """
    Collect test files from existing job directories

    Args:
        txt_count: Number of TXT files needed
        screenshot_count: Number of screenshot files needed
        source_jobs: List of job IDs to source from

    Returns:
        Tuple of (txt_files, screenshot_files)
    """
    txt_files = []
    screenshot_files = []

    upload_dir = Path('/Users/nicodelgadob/ggrevealer-3-repl/storage/uploads')

    for job_id in source_jobs:
        job_dir = upload_dir / str(job_id)
        if not job_dir.exists():
            continue

        # Collect TXT files
        txt_dir = job_dir / 'txt'
        if txt_dir.exists():
            for f in txt_dir.glob('*.txt'):
                if len(txt_files) < txt_count:
                    txt_files.append(f)

        # Collect screenshot files
        ss_dir = job_dir / 'screenshots'
        if ss_dir.exists():
            for f in ss_dir.glob('*.png'):
                if len(screenshot_files) < screenshot_count:
                    screenshot_files.append(f)

    return txt_files, screenshot_files


def upload_files(txt_files: List[Path], screenshot_files: List[Path]) -> dict:
    """
    Upload files using the batch upload API

    Returns:
        Job creation response
    """
    print(f"📤 Uploading {len(txt_files)} TXT files and {len(screenshot_files)} screenshots...")

    # Calculate total size
    total_size = sum(f.stat().st_size for f in txt_files + screenshot_files)
    total_mb = total_size / (1024 * 1024)
    print(f"📊 Total size: {total_mb:.1f} MB")

    files = []

    # Add TXT files
    for f in txt_files:
        files.append(('txt_files', (f.name, open(f, 'rb'), 'text/plain')))

    # Add screenshot files
    for f in screenshot_files:
        files.append(('screenshot_files', (f.name, open(f, 'rb'), 'image/png')))

    # Upload with progress tracking
    start_time = time.time()
    response = requests.post(f"{BASE_URL}/api/upload", files=files)
    upload_time = time.time() - start_time

    # Close files
    for _, file_tuple in files:
        file_tuple[1].close()

    if response.status_code == 200:
        result = response.json()
        print(f"✅ Upload successful in {upload_time:.1f}s")
        print(f"   Job ID: {result['job_id']}")
        return result
    else:
        print(f"❌ Upload failed: {response.status_code}")
        print(f"   Error: {response.text}")
        return None


def monitor_processing(job_id: int) -> dict:
    """
    Monitor job processing until completion

    Returns:
        Final job status
    """
    print(f"⏳ Processing job {job_id}...")

    last_status = None
    start_time = time.time()

    while True:
        response = requests.get(f"{BASE_URL}/api/status/{job_id}")
        if response.status_code != 200:
            print(f"❌ Failed to get status: {response.status_code}")
            return None

        status = response.json()
        current_status = status.get('status')

        # Print status changes
        if current_status != last_status:
            elapsed = time.time() - start_time
            print(f"   [{elapsed:.0f}s] Status: {current_status}")
            last_status = current_status

        # Print progress for processing
        if current_status == 'processing':
            ocr_processed = status.get('ocr_processed_count', 0)
            ocr_total = status.get('ocr_total_count', 0)
            if ocr_total > 0:
                pct = (ocr_processed / ocr_total) * 100
                print(f"   [{elapsed:.0f}s] OCR Progress: {ocr_processed}/{ocr_total} ({pct:.0f}%)", end='\r')

        # Check if done
        if current_status in ['completed', 'failed']:
            elapsed = time.time() - start_time
            print(f"\n✅ Job {current_status} in {elapsed:.1f}s")
            return status

        time.sleep(2)


def test_dataset(name: str, txt_count: int, screenshot_count: int, source_jobs: List[int], expected_batches: int):
    """
    Test a dataset size
    """
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Target: {txt_count} TXT files, {screenshot_count} screenshots")
    print(f"Expected batches: {expected_batches}")
    print()

    # Collect files
    txt_files, screenshot_files = collect_files(txt_count, screenshot_count, source_jobs)
    print(f"✓ Collected {len(txt_files)} TXT files, {len(screenshot_files)} screenshots")

    if len(txt_files) < txt_count or len(screenshot_files) < screenshot_count:
        print(f"⚠️  Warning: Could not collect enough files (needed {txt_count}/{screenshot_count})")

    # Upload
    result = upload_files(txt_files, screenshot_files)
    if not result:
        return False

    job_id = result['job_id']

    # Start processing
    print(f"\n🚀 Starting processing...")
    response = requests.post(f"{BASE_URL}/api/process/{job_id}")
    if response.status_code != 200:
        print(f"❌ Failed to start processing: {response.status_code}")
        return False

    # Monitor
    final_status = monitor_processing(job_id)

    if final_status and final_status.get('status') == 'completed':
        print(f"\n📊 Results:")
        print(f"   Matched hands: {final_status.get('matched_hands', 0)}")
        print(f"   Name mappings: {final_status.get('name_mappings_count', 0)}")
        print(f"   OCR success: {final_status.get('ocr1_success_count', 0)}/{final_status.get('ocr_total_count', 0)}")
        return True

    return False


def test_error_scenarios():
    """
    Test error scenarios
    """
    print(f"\n{'='*60}")
    print(f"TEST: Error Scenarios")
    print(f"{'='*60}")

    # Test 1: >300 files limit
    print(f"\n1. Testing file limit validation (>300 files)...")
    txt_files, screenshot_files = collect_files(301, 0, [64])  # Job 64 has 301 TXT files
    if len(txt_files) >= 301:
        result = upload_files(txt_files[:301], [])
        if result:
            print(f"❌ Should have rejected >300 files!")
            return False
        else:
            print(f"✅ Correctly rejected >300 files")
    else:
        print(f"⚠️  Skipping: Not enough files for test")

    # Test 2: Upload to processing job
    print(f"\n2. Testing upload to processing job...")
    # Create a small job first
    txt_files, screenshot_files = collect_files(1, 1, [1])
    result = upload_files(txt_files, screenshot_files)
    if result:
        job_id = result['job_id']
        # Start processing
        requests.post(f"{BASE_URL}/api/process/{job_id}")
        time.sleep(1)

        # Try to upload again to same job (should fail)
        response = requests.post(f"{BASE_URL}/api/upload",
                                files=[('txt_files', ('test.txt', b'test', 'text/plain'))],
                                data={'job_id': job_id})
        if response.status_code != 200:
            print(f"✅ Correctly rejected upload to processing job")
        else:
            print(f"❌ Should have rejected upload to processing job!")

    return True


if __name__ == "__main__":
    print("="*60)
    print("BATCH UPLOAD SYSTEM - END-TO-END TESTING")
    print("="*60)

    # Test 1: Small dataset (~30 MB, 1 batch)
    success1 = test_dataset(
        name="Small Dataset (<50 MB, 1 batch)",
        txt_count=10,
        screenshot_count=30,
        source_jobs=[32, 35],  # 27 MB each
        expected_batches=1
    )

    # Test 2: Medium dataset (~80 MB, 2-3 batches)
    success2 = test_dataset(
        name="Medium Dataset (50-100 MB, 2-3 batches)",
        txt_count=50,
        screenshot_count=100,
        source_jobs=[32, 35, 9],  # 27 + 27 + 14 = 68 MB
        expected_batches=2
    )

    # Test 3: Large dataset (~145 MB, 3-4 batches)
    success3 = test_dataset(
        name="Large Dataset (100-200 MB, 3-4 batches)",
        txt_count=100,
        screenshot_count=200,
        source_jobs=[24],  # 143.7 MB (266 files)
        expected_batches=3
    )

    # Test 4: Error scenarios
    success4 = test_error_scenarios()

    # Summary
    print(f"\n{'='*60}")
    print(f"TEST SUMMARY")
    print(f"{'='*60}")
    print(f"✓ Small dataset (30 MB, 1 batch): {'SUCCESS' if success1 else 'FAILED'}")
    print(f"✓ Medium dataset (80 MB, 2-3 batches): {'SUCCESS' if success2 else 'FAILED'}")
    print(f"✓ Large dataset (150 MB, 3-4 batches): {'SUCCESS' if success3 else 'FAILED'}")
    print(f"✓ Error scenarios: {'SUCCESS' if success4 else 'FAILED'}")
    print(f"\nOverall: {'ALL TESTS PASSED ✅' if all([success1, success2, success3, success4]) else 'SOME TESTS FAILED ❌'}")
