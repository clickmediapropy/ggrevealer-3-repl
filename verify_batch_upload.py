#!/usr/bin/env python3
"""
Verification script for batch upload system
Tests upload mechanism without running full processing pipeline
"""

import requests
import json
from pathlib import Path
from typing import List, Tuple

BASE_URL = "http://localhost:8000"


def collect_files(txt_count: int, screenshot_count: int, source_jobs: List[int]) -> Tuple[List[Path], List[Path]]:
    """Collect test files from existing job directories"""
    txt_files = []
    screenshot_files = []

    upload_dir = Path('/Users/nicodelgadob/ggrevealer-3-repl/storage/uploads')

    for job_id in source_jobs:
        job_dir = upload_dir / str(job_id)
        if not job_dir.exists():
            continue

        txt_dir = job_dir / 'txt'
        if txt_dir.exists():
            for f in txt_dir.glob('*.txt'):
                if len(txt_files) < txt_count:
                    txt_files.append(f)

        ss_dir = job_dir / 'screenshots'
        if ss_dir.exists():
            for f in ss_dir.glob('*.png'):
                if len(screenshot_files) < screenshot_count:
                    screenshot_files.append(f)

    return txt_files, screenshot_files


def test_upload(name: str, txt_count: int, screenshot_count: int, source_jobs: List[int]):
    """Test file upload without processing"""
    print(f"\n{'='*70}")
    print(f"TEST: {name}")
    print(f"{'='*70}")

    # Collect files
    txt_files, screenshot_files = collect_files(txt_count, screenshot_count, source_jobs)
    actual_txt = len(txt_files)
    actual_ss = len(screenshot_files)

    print(f"Target: {txt_count} TXT, {screenshot_count} screenshots")
    print(f"Collected: {actual_txt} TXT, {actual_ss} screenshots")

    if actual_txt == 0 or actual_ss == 0:
        print(f"❌ SKIP: Not enough files")
        return None

    # Calculate size
    total_size = sum(f.stat().st_size for f in txt_files + screenshot_files)
    total_mb = total_size / (1024 * 1024)
    print(f"Total size: {total_mb:.1f} MB")

    # Prepare files for upload
    files = []
    for f in txt_files:
        files.append(('txt_files', (f.name, open(f, 'rb'), 'text/plain')))
    for f in screenshot_files:
        files.append(('screenshot_files', (f.name, open(f, 'rb'), 'image/png')))

    # Upload
    print(f"📤 Uploading...")
    try:
        response = requests.post(f"{BASE_URL}/api/upload", files=files, timeout=60)

        # Close files
        for _, file_tuple in files:
            file_tuple[1].close()

        if response.status_code == 200:
            result = response.json()
            print(f"✅ Upload successful!")
            print(f"   Job ID: {result['job_id']}")
            print(f"   TXT files: {result['txt_files_count']}")
            print(f"   Screenshots: {result['screenshot_files_count']}")

            # Check if batching occurred (would be logged in server console)
            expected_batches = max(1, int(total_mb / 50))  # Rough estimate: 50 MB per batch
            print(f"   Expected batches: ~{expected_batches}")
            print(f"   ℹ️  Check server console for batch progress logs")

            return result
        elif response.status_code == 413:
            print(f"❌ Upload failed with 413 (Payload Too Large)")
            print(f"   This means the batch upload fix is NOT working!")
            return None
        else:
            print(f"❌ Upload failed: {response.status_code}")
            try:
                print(f"   Error: {response.json()}")
            except:
                print(f"   Error: {response.text[:200]}")
            return None

    except requests.exceptions.Timeout:
        print(f"⚠️  Upload timed out (60s) - large dataset may need longer timeout")
        return None
    except Exception as e:
        print(f"❌ Upload failed with exception: {e}")
        return None


def test_file_limit():
    """Test >300 files validation"""
    print(f"\n{'='*70}")
    print(f"TEST: File Limit Validation (>300 files)")
    print(f"{'='*70}")

    # Try to collect 301+ files
    txt_files, screenshot_files = collect_files(301, 0, [64, 24, 25])

    if len(txt_files) < 301:
        print(f"⚠️  SKIP: Not enough files (need 301, have {len(txt_files)})")
        return

    print(f"Attempting to upload {len(txt_files)} files...")

    files = []
    for f in txt_files[:301]:
        files.append(('txt_files', (f.name, open(f, 'rb'), 'text/plain')))

    response = requests.post(f"{BASE_URL}/api/upload", files=files, timeout=30)

    # Close files
    for _, file_tuple in files:
        file_tuple[1].close()

    if response.status_code == 400:
        error = response.json()
        if 'exceed' in error.get('detail', '').lower():
            print(f"✅ Correctly rejected with validation error")
            print(f"   Error: {error.get('detail')}")
        else:
            print(f"⚠️  Rejected but with unexpected error: {error.get('detail')}")
    else:
        print(f"❌ Should have rejected >300 files! Got status: {response.status_code}")


if __name__ == "__main__":
    print("="*70)
    print("BATCH UPLOAD VERIFICATION")
    print("="*70)
    print("This script tests the batch upload mechanism without full processing.")
    print("Monitor the server console for batch progress logs.")
    print()

    # Test 1: Small dataset
    result1 = test_upload(
        name="Small Dataset (~30 MB, expected 1 batch)",
        txt_count=10,
        screenshot_count=30,
        source_jobs=[32, 35]
    )

    # Test 2: Medium dataset
    result2 = test_upload(
        name="Medium Dataset (~80 MB, expected 2-3 batches)",
        txt_count=80,
        screenshot_count=80,
        source_jobs=[32, 35, 9]
    )

    # Test 3: Large dataset
    result3 = test_upload(
        name="Large Dataset (~145 MB, expected 3-4 batches)",
        txt_count=150,
        screenshot_count=150,
        source_jobs=[24, 25]
    )

    # Test 4: File limit
    test_file_limit()

    # Summary
    print(f"\n{'='*70}")
    print(f"VERIFICATION SUMMARY")
    print(f"{'='*70}")
    print(f"Small dataset (30 MB): {'✅ SUCCESS' if result1 else '❌ FAILED'}")
    print(f"Medium dataset (80 MB): {'✅ SUCCESS' if result2 else '❌ FAILED'}")
    print(f"Large dataset (145 MB): {'✅ SUCCESS' if result3 else '❌ FAILED'}")
    print()
    print(f"Key verification: Did any test fail with 413 error?")
    print(f"If NO 413 errors: ✅ Batch upload fix is working!")
    print(f"If YES 413 errors: ❌ Batch upload fix needs investigation")
    print()
    print(f"Next steps:")
    print(f"1. Review server console logs for batch progress messages")
    print(f"2. Run processing on one of the created jobs to verify end-to-end")
    print(f"3. Test via web UI at http://localhost:8000/app")
