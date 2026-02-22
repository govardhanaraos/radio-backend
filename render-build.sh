#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# Remove --with-deps because you don't have sudo permissions
playwright install chromium