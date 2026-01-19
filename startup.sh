#!/bin/bash
# Azure App Service startup script

# Set Python path to include src directory
export PYTHONPATH=/home/site/wwwroot:$PYTHONPATH

# Start uvicorn on port 8000 (Azure expects this)
python -m uvicorn src.api.medical_invoice_api:app --host 0.0.0.0 --port 8000
