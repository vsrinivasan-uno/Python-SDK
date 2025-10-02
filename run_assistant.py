#!/usr/bin/env python3
"""Convenience script to run the Misty Aicco Assistant.

This script can be run from the project root directory.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Import and run the main application
from src.misty_aicco_assistant import main

if __name__ == "__main__":
    main()

