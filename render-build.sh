#!/usr/bin/env bash
# exit on error
set -o errexit

# Install python dependencies
pip install -r requirements.txt

# Install Playwright browsers AND the required system dependencies
playwright install --with-deps chromium