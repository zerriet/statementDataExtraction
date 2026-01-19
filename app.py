# Azure App Service entry point
# This file provides a single entry point for uvicorn to import the app

import sys
import os

# Ensure the src directory is in the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the FastAPI app
from src.api.medical_invoice_api import app

# Expose the app for uvicorn
__all__ = ["app"]
