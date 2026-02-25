#!/bin/bash

# Simple Rasa start script - Just starts the server
# For quick testing without actions server

cd "$(dirname "$0")"

echo "Starting Rasa server on port 5005..."
rasa run --enable-api --cors "*" --port 5005
