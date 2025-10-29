"""
Configuration file for GGRevealer application.

Contains pricing information and other app-wide constants.
"""

# Google Gemini API Pricing (Updated: September 2025)
# Source: https://ai.google.dev/pricing
# Model: gemini-2.5-flash-image

# Cost per image processed (in USD)
GEMINI_COST_PER_IMAGE = 0.00001315  # $0.00001315 per image

# Model name used for OCR
GEMINI_MODEL = "gemini-2.5-flash-image"

# Note: Update GEMINI_COST_PER_IMAGE when Google changes pricing
# Last updated: September 2025
