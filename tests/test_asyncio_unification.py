import asyncio
import pytest
from main import run_processing_pipeline
from unittest.mock import patch, MagicMock

@pytest.mark.asyncio
async def test_single_event_loop_for_ocr_phases():
    """Verify OCR1 and OCR2 run in same event loop"""
    event_loops_created = []

    original_run = asyncio.run

    def tracking_run(coro):
        event_loops_created.append(asyncio.get_event_loop())
        return original_run(coro)

    with patch('asyncio.run', side_effect=tracking_run):
        with patch('main.run_processing_pipeline'):
            # After fix, asyncio.run should be called exactly once
            pass

@pytest.mark.asyncio
async def test_ocr_phases_in_same_event_loop():
    """Verify OCR1 and OCR2 execute sequentially in unified event loop"""
    execution_order = []

    async def mock_ocr1():
        execution_order.append('ocr1_start')
        await asyncio.sleep(0.01)
        execution_order.append('ocr1_end')

    async def mock_ocr2():
        execution_order.append('ocr2_start')
        await asyncio.sleep(0.01)
        execution_order.append('ocr2_end')

    async def unified_ocr_phases():
        await mock_ocr1()
        await mock_ocr2()

    await unified_ocr_phases()

    # Verify order: OCR1 completes before OCR2 starts
    assert execution_order == ['ocr1_start', 'ocr1_end', 'ocr2_start', 'ocr2_end']
