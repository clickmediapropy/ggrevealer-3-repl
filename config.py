"""
Configuration file for GGRevealer application.

Contains pricing information and other app-wide constants.
"""

# Google Gemini API Pricing (Updated: October 2025)
# Source: Real usage data from Google Cloud Billing (Oct 1-29, 2025)
# Model: gemini-2.5-flash-image

# Cost per screenshot processed (in USD)
# This includes both OCR1 (Hand ID) + OCR2 (Player Details) operations
# Based on: 916 screenshots = $15.02 total cost
GEMINI_COST_PER_IMAGE = 0.0164  # $0.0164 per screenshot (dual OCR average)

# Model name used for OCR
GEMINI_MODEL = "gemini-2.5-flash-image"

# Note: This cost reflects the complete processing pipeline:
# - OCR1: Always runs on all screenshots
# - OCR2: Runs only on matched screenshots (~50-80%)
# Last updated: October 29, 2025 (real billing data)
