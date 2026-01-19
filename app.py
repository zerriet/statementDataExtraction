# Azure App Service entry point
# This file provides a single entry point for uvicorn to import the app

import sys
import os

# Get the directory containing this file
app_dir = os.path.dirname(os.path.abspath(__file__))

# Add the app directory to Python path (for 'src' imports)
if app_dir not in sys.path:
    sys.path.insert(0, app_dir)

# Add the src directory to Python path (for 'parsers', 'inference' imports)
src_dir = os.path.join(app_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Import the FastAPI app
from src.api.medical_invoice_api import app

# Expose the app for uvicorn
__all__ = ["app"]
