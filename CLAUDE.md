# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Backend (FastAPI — runs on port 3000)
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 3000        # dev with hot reload
uvicorn main:app --host 0.0.0.0 --port 3000  # production
```

Docker:
```bash
cd backend
docker build -t chatbot-backend .
docker-compose up
```

### Frontend (Vite + React — proxies to port 3000)
```bash
cd frontend
npm install
npm run dev      # dev server
npm run build    # production build
npm run lint     # ESLint
npm run preview  # preview production build
```

### Rasa NLU (runs on port 5005)
```bash
cd rasa-bot
rasa train                    # retrain model after editing nlu.yml/domain.yml
rasa run --enable-api         # start NLU server (required for backend)
rasa shell                    # interactive test
rasa test                     # run test stories in tests/test_stories.yml
```

### Required environment variables (backend `.env`)
```
OPENAI_API_KEY=
RASA_URL=http://localhost:5005
CONFIDENCE_THRESHOLD=0.90        # Rasa confidence cutoff; below this routes to OpenAI
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
ZOOM_ACCOUNT_ID=
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
PORT=3000
```

Google Calendar requires `backend/google_credentials.json` and `backend/google_token.json` (OAuth2 credentials file, not in repo).

## Architecture

### Request Routing — the core decision tree (`backend/main.py:get_reply()`)

Every incoming message goes through a 4-priority waterfall:

1. **Active booking flow** — if `context['current_flow']` is set, the user is mid-booking. Side questions with ≥90% Rasa confidence get answered by a specialized agent while the flow is preserved. Everything else continues the flow.
2. **High confidence (≥ `CONFIDENCE_THRESHOLD`)** — route to a specialized agent in `AgentRouter` (free, instant, deterministic).
3. **Low confidence** — call OpenAI GPT-4 (`ask_openai()`) with the last 15 conversation turns as history.
4. **OpenAI unavailable** — `agent_router.get_fallback_response()`.

### Rasa is NLU-only

Rasa is called only at `/model/parse` (stateless intent + confidence extraction). Its dialogue manager, forms, tracker, and `booking_form` are **intentionally bypassed** — the backend never calls `/webhooks/rest/webhook`. All session state lives in `backend/main.py:conversations{}` (in-memory, keyed by `sender`), managed by `AgentRouter.context_manager` in `agents.py`.

The custom action `ActionBookAppointment` in `rasa-bot/actions/actions.py` and the `action_endpoint` in `rasa-bot/endpoints.yml` are both disabled/commented out.

### Multi-agent system (`backend/agents.py`)

`AgentRouter.route(intent, message, sender)` dispatches to one of ~15 specialized agents (e.g., `BookingAgent`, `PricingAgent`, `HoursAgent`). Each agent holds bilingual (EN/AR) response templates and accesses `ClinicConfig`. The booking flow is a state machine that collects: `name → email → phone → date → time → consultation_type`, then calls `google_calendar_service.book_appointment_fast()`.

### Clinic configuration (`backend/config.yml` + `backend/config_loader.py`)

All clinic-specific data (pricing, hours, doctor info, locations, appointment durations) lives in `config.yml`. `ClinicConfig` (a dataclass) wraps it with typed properties. Pricing is location-based — WhatsApp GPS coordinates are reverse-geocoded via `location_service.py` to pick the right pricing tier.

### Multi-channel entry points

The same `get_reply()` core is shared by:
- `POST /chat` — web frontend
- `POST /sms/webhook` — Twilio SMS
- `POST /whatsapp/webhook` — Twilio WhatsApp (also handles GPS location shares)

### RAG service (disabled)

`backend/rag_service.py` is a fully written FAISS + `sentence-transformers` RAG pipeline over `knowledge_base/` (treatment protocol documents). It is not wired into any request path. To enable it, uncomment `sentence-transformers`, `faiss-cpu`, and `numpy` in `requirements.txt`.

### Frontend state

Redux Toolkit manages all chat state in `frontend/src/store/slices/chatSlice.js`. The `sendMessage` thunk calls `POST /chat` with `{message, sender, name}`. `sender` is a `nanoid`-based session ID generated once per page load. Bot messages can include `buttons[]` (one-use pill buttons) and a `pick_date` action type that renders a date picker.

## Key Constraints

- **No Rasa dialogue management.** Do not route messages through `/webhooks/rest/webhook` — it activates Rasa's tracker and conflicts with the backend's own state.
- **`config.yml` is the single source of truth** for clinic info. Agent response templates read from `ClinicConfig`, not hardcoded strings.
- **In-memory session state** (`conversations{}` in `main.py`) is lost on restart. There is no database.
- **Online consultations** (Zoom) are Thursday–Saturday; **in-person** is Sunday–Wednesday. This distinction is enforced in availability logic and the booking flow.
- The `CONFIDENCE_THRESHOLD` env var (default `0.90`) controls the Rasa→OpenAI cutoff and can be tuned without code changes.
