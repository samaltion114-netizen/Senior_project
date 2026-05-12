# nahd_backend

Production-oriented Django 4.2 + DRF backend for the Nahd senior project scenario.

## Stack
- Python 3.11+
- Django 4.2
- Django REST Framework + SimpleJWT
- PostgreSQL
- Redis
- Celery worker + beat
- Gunicorn + Nginx

## Apps
- `accounts`: custom user + student/expert profiles + registration
- `core`: objectives/tasks
- `ai`: interview expert-system, tagging/checklists, time estimate, event logs, Celery tasks
- `scheduling`: optimized session allocation
- `proofs`: session completion, proof upload/analysis, programming questions, todos, challenges

## Run With Docker
```bash
cp .env.example .env
docker-compose up --build
```

API:
- `http://localhost/api/docs/`
- `http://localhost/api/schema/`
- Django admin: `http://localhost/admin/`

## Local Test Run
```bash
pytest -q
```
or
```bash
make test
```

## Demo Flow Script
```bash
bash scripts/demo_flow.sh
```

Uses `tests/fixtures/screenshot1.png` and executes:
register -> interview -> objective -> tasks -> schedule -> complete session -> proof analysis.

## Environment Variables
- `DEBUG`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `REDIS_URL`
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `AI_PROVIDER` (`mock` or `openai`)
- `PROOF_CONFIDENCE_THRESHOLD`

No secrets are committed.

## AI Feature APIs (from your 5 docs)

### 1) Expert Interview Goal Selection
- `POST /api/interview/start/`
- `POST /api/interview/message/`

### 2) Smart Time Estimation + Scheduling
- `POST /api/ai/time-estimate/`
- `POST /api/objectives/{id}/tasks/` (auto estimation)
- `POST /api/schedule/optimize/`

Time-estimation dataset used by the backend:
- `ai/data/Informatics_task_times_synthetic.csv`
- configured through `AI_TASK_TIME_DATASET`
- treated as backend AI data, not a model weight file

### 3) Intelligent Tagging + Checklist
- `POST /api/ai/tagging/informatics/`
- `POST /api/ai/tagging/legal/`

### 4) Daily Micro-Challenges
- `POST /api/ai/challenges/generate/`
- `GET /api/challenges/`

### 5) Proof Verification + Bug Detection
- `POST /api/sessions/{id}/complete/` (multipart image + explanation)
- `GET /api/proofs/{id}/analysis/`

## Local Weight Models (Your Own Weights)

Put your weight files in:
- `ai_model_weights/` (local)
- mounted in Docker as `/app/ai_model_weights`

Supported file extensions discovered by API:
- `.pt`, `.pth`, `.bin`, `.onnx`, `.safetensors`, `.pkl`, `.joblib`, `.gguf`

Model management APIs:
- `GET /api/ai/models/weights/` : list discovered files + active selections
- `POST /api/ai/models/select/` : activate model per capability

### GGUF Mindmap Runtime (llama.cpp)

Mindmap generation supports local GGUF inference through a running `llama-server`.

Required runtime env vars:
- `AI_LOCAL_INFERENCE_URL` (default `http://127.0.0.1:8080`)
- `AI_LOCAL_INFERENCE_TIMEOUT` (default `45`)

Run llama-server (Windows example):
```bash
"C:\Users\ASUS\Desktop\llama.cpp\llama.cpp\build\bin\Release\llama-server.exe" -m "C:\Users\ASUS\Senior_project\Project_root\ai_model_weights\mindmap-ai-q8.gguf" -c 4096 --host 127.0.0.1 --port 8080
```

Mindmap APIs:
- `GET /api/ai/mindmap/svg/` : return integrated SVG file
- `POST /api/ai/mindmap/generate/` : generate JSON mindmap from topic/context

Mindmap generate body:
```json
{
  "topic": "Academic Text Analysis",
  "context": "boolean retrieval regex wildcard indices corpus JSON",
  "max_branches": 6
}
```

How to verify real GGUF inference:
- response contains `"inference": "gguf_runtime"` and `"provider": "local"`
- if runtime is unavailable/invalid output, backend safely returns `"inference": "fallback_mock"`

Capabilities:
- `all`
- `interview`
- `tagging`
- `time_estimation`
- `scheduling`
- `proof_analysis`
- `challenge_generation`

Example select request:
```bash
curl -X POST http://localhost/api/ai/models/select/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "capability": "interview",
    "provider": "local",
    "model_name": "my_interview_model",
    "weight_path": "/app/ai_model_weights/interview_v1.onnx",
    "metadata": {"framework":"onnx"}
  }'
```

## Required Core Endpoints
- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `POST /api/auth/update-fcm-token/`
- `GET /api/objectives/`
- `POST /api/objectives/`
- `GET/PATCH/DELETE /api/objectives/{id}/`
- `POST /api/objectives/{id}/tasks/`
- `POST /api/objectives/{id}/generate-tasks/`
- `GET/PATCH/DELETE /api/tasks/{id}/`
- `POST /api/tasks/{id}/complete/`
- `POST /api/tasks/{id}/comments/`
- `POST /api/schedule/optimize/`
- `POST /api/sessions/{id}/complete/`
- `GET /api/proofs/{id}/analysis/`
- `GET /api/challenges/`
- `GET /api/experts/?search=<name>`
- `POST /api/assignments/request/`
- `POST /api/trainer/assignments/{id}/accept/`
- `POST /api/trainer/assignments/{id}/reject/`
- `GET /api/notifications/`
- `GET /api/leaderboard/?filter=daily`
- `GET /api/users/{id}/badges/`
- `POST /api/payments/intent/`
- `GET /api/payments/`
- `POST /api/payments/webhook/`
- `GET /api/assignments/`
- `GET /api/chat/threads/`
- `GET/POST /api/chat/threads/{id}/messages/`

## Professional Non-AI Features Added

### API Versioning
- All existing APIs are available under:
  - `/api/...`
  - `/api/v1/...`

### Account Security Flows
- `POST /api/auth/verify-email/request/`
- `POST /api/auth/verify-email/confirm/`
- `POST /api/auth/password-reset/request/`
- `POST /api/auth/password-reset/confirm/`

Registration now creates email verification token (development output in console).

### Health Endpoints
- `GET /api/health/live/`
- `GET /api/health/ready/` (includes DB readiness check)

### Gamification + Collaboration
- XP/streak fields on users
- task status/type/difficulty/xp/youtube links
- leaderboard + badges + activity log
- expert assignment request/accept/reject flow
- notification records for assignment actions, proof analysis, decomposition, and gamification
- task comments gated by active expert assignment
- active-assignment chat threads and messages
- periodic reminder jobs for inactivity, streak risk, session reminders, and assignment expiry

### Payments
- `POST /api/payments/intent/`
- `GET /api/payments/`
- `POST /api/payments/webhook/`
- uses Stripe when configured, otherwise returns a mock `client_secret` for backend/dev flow
- stores payment records and updates statuses via webhook payloads

### Standardized Error Responses
All DRF errors now use one shape:
```json
{
  "success": false,
  "message": "Validation error.",
  "errors": {...},
  "status_code": 400
}
```

## Example Curl

Register:
```bash
curl -X POST http://localhost/api/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"username":"student1","password":"pass12345","email":"student1@example.com","role":"student","major":"IT"}'
```

Start interview:
```bash
curl -X POST http://localhost/api/interview/start/ \
  -H "Authorization: Bearer <token>"
```

Send interview message:
```bash
curl -X POST http://localhost/api/interview/message/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"conversation_id":1,"message":"I want training in AI"}'
```

Create task:
```bash
curl -X POST http://localhost/api/objectives/1/tasks/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"title":"Implement a classifier","description":"build","metadata":{},"order":1}'
```

Upload proof:
```bash
curl -X POST http://localhost/api/sessions/5/complete/ \
  -H "Authorization: Bearer <token>" \
  -F "image=@tests/fixtures/screenshot1.png" \
  -F "explanation=I completed the session"
```

## Postman
See `docs/postman/Nahd.postman_collection.json`.

## Software Diagrams
See `docs/diagrams/README.md` for:
- ERD
- Component diagram
- Block architecture diagram
- Deployment diagram
- End-to-end sequence diagram
- State diagrams
- Permissions matrix

## Security Notes
- JWT authentication via SimpleJWT.
- Role checks for student endpoints.
- Upload validation (mime + size).
- Interview endpoint throttle enabled.
- API keys expected from environment variables only.

## Storage
Default: local disk media storage.

To switch to S3:
1. install `django-storages[boto3]`
2. configure storage backend in settings
3. add AWS env vars.

## Celery Tasks
- `ai.tasks.analyze_proof_task`
- `ai.tasks.generate_daily_challenges_task`
- Management command: `python manage.py generate_daily_challenges`

## How AI Features Work (technical summary)

`ai/services.py` defines interface-style classes (`InterviewAgent`, `ObjectiveScorer`, `TimeEstimator`, `ScheduleOptimizer`, `ProofAnalyzer`, `ChallengeGenerator`) and a factory `get_ai_service()`.

`MockAIService` is deterministic and used for tests/demo:
- Interview: rule-based completion + one suggested objective
- Tagging: top-K tags + fixed educational checklist + references
- Time estimation: heuristic regression-like prediction
- Scheduling: greedy optimizer honoring availability, daily limits, breaks, no overlap
- Proof analysis: text/image-caption similarity + quality metrics + threshold decision
- Mismatch flow: generates `ProgrammingQuestion` and `TodoItem` list
- Challenges: adaptive micro-task generation from open issues

`OpenAIAdapter` is a swappable adapter shell with TODOs for real provider wiring:
- inject API client
- replace mock heuristics with LLM/Vision/OCR pipelines
- keep same return contracts to avoid API/controller changes.
