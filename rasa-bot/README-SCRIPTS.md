# Rasa Start Scripts

## Available Scripts

### 1. `start-rasa.sh` (Recommended)
Full-featured start script that:
- Checks if Rasa is installed
- Trains model if not present (with option to retrain)
- Starts Actions Server on port 5055
- Starts Rasa Server on port 5005 with API and CORS enabled
- Handles graceful shutdown of both servers

**Usage:**
```bash
cd rasa-bot
./start-rasa.sh
```

**Features:**
- Auto-trains model if missing
- Runs actions server in background
- Logs actions server output to `logs/actions.log`
- Press Ctrl+C to stop both servers

### 2. `start-simple.sh`
Minimal script that just starts the Rasa server without actions.

**Usage:**
```bash
cd rasa-bot
./start-simple.sh
```

## Prerequisites

Make sure you have Rasa installed:
```bash
pip install rasa
```

## Manual Commands

### Train the model:
```bash
cd rasa-bot
rasa train
```

### Start Rasa server only:
```bash
cd rasa-bot
rasa run --enable-api --cors "*" --port 5005
```

### Start Actions server:
```bash
cd rasa-bot
rasa run actions --port 5055
```

### Test the bot interactively:
```bash
cd rasa-bot
rasa shell
```

## Endpoints

Once started, Rasa will be available at:
- **API**: http://localhost:5005
- **Webhook**: http://localhost:5005/webhooks/rest/webhook
- **Actions**: http://localhost:5055 (if using start-rasa.sh)

## Troubleshooting

### Port already in use:
```bash
# Kill existing Rasa processes
pkill -f "rasa run"
```

### View actions server logs:
```bash
tail -f logs/actions.log
```
