#!/bin/bash

# ===================================================================
# Rasa Start Script for Healthcare Chatbot
# This script trains the model (if needed) and starts Rasa services
# ===================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
RASA_PORT=5005
ACTION_PORT=5055
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Healthcare Chatbot - Rasa Startup${NC}"
echo -e "${GREEN}========================================${NC}"

# Change to rasa-bot directory
cd "$SCRIPT_DIR"

# Check if rasa is installed
if ! command -v rasa &> /dev/null; then
    echo -e "${RED}Error: Rasa is not installed!${NC}"
    echo -e "${YELLOW}Install it with: pip install rasa${NC}"
    exit 1
fi

# Check if model exists
if [ ! -d "models" ] || [ -z "$(ls -A models 2>/dev/null)" ]; then
    echo -e "${YELLOW}No trained model found. Training new model...${NC}"
    rasa train
    echo -e "${GREEN}✓ Model trained successfully${NC}"
else
    echo -e "${GREEN}✓ Trained model found${NC}"

    # Ask if user wants to retrain
    read -p "Do you want to retrain the model? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Retraining model...${NC}"
        rasa train
        echo -e "${GREEN}✓ Model retrained successfully${NC}"
    fi
fi

# Kill any existing Rasa processes
echo -e "${YELLOW}Checking for existing Rasa processes...${NC}"
pkill -f "rasa run" 2>/dev/null || true
pkill -f "rasa run actions" 2>/dev/null || true
sleep 2

# Start Rasa Actions Server in background
echo -e "${GREEN}Starting Rasa Actions Server on port ${ACTION_PORT}...${NC}"
rasa run actions --port $ACTION_PORT > logs/actions.log 2>&1 &
ACTION_PID=$!
echo -e "${GREEN}✓ Actions server started (PID: ${ACTION_PID})${NC}"

# Wait for actions server to be ready
sleep 3

# Start Rasa Server
echo -e "${GREEN}Starting Rasa Server on port ${RASA_PORT}...${NC}"
echo -e "${YELLOW}API will be available at: http://localhost:${RASA_PORT}${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop both servers${NC}"
echo -e "${GREEN}========================================${NC}"

# Trap Ctrl+C to kill both processes
trap "echo -e '\n${YELLOW}Shutting down...${NC}'; kill $ACTION_PID 2>/dev/null; pkill -f 'rasa run' 2>/dev/null; exit" INT TERM

# Start Rasa server (this will run in foreground)
rasa run --enable-api --cors "*" --port $RASA_PORT --debug
