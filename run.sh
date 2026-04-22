#!/bin/bash

set -e
source venv/bin/activate
source .env
set +e

echo "Starting Telegram Bot..."

python main.py
