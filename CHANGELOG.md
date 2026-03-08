# CHANGELOG

## 1.0.0 - 2026-02-22

### Added
- Full Django project scaffold: `nahd_backend`
- Apps: `accounts`, `core`, `ai`, `scheduling`, `proofs`, `reviews`
- Custom `User` model with role flags (`is_student`, `is_expert`, `is_trainer`)
- Domain models:
  - `StudentProfile`, `ExpertProfile`
  - `Objective`, `Task`
  - `Session`
  - `Proof`, `ProgrammingQuestion`, `TodoItem`, `Challenge`
  - `AdminReview`
  - `AIEventLog`, `InterviewConversation`, `InterviewMessage`
- API endpoints for:
  - registration and JWT auth
  - interview start/message
  - objective list/create
  - task creation with AI time estimate
  - schedule optimization
  - session completion with proof upload
  - proof analysis retrieval
  - trainer review
  - challenge list
  - AI tagging/checklist (informatics/legal)
  - standalone time estimate
  - challenge generation
- Role-based permissions and interview throttling
- Upload validation for proof images
- Celery tasks:
  - `analyze_proof_task`
  - `generate_daily_challenges_task`
- Management command: `generate_daily_challenges`
- Docker stack:
  - Django/Gunicorn
  - Nginx
  - Postgres
  - Redis
  - Celery worker + beat
- Fixtures and demo script:
  - `fixtures/initial_data.json`
  - `tests/fixtures/screenshot1.png`
  - `scripts/demo_flow.sh`
- Tests (`pytest`) including full end-to-end demo flow
- OpenAPI schema support via DRF Spectacular
- Postman collection and README documentation
- API versioning path support (`/api/v1/...`)
- Email verification token flow endpoints
- Password reset token flow endpoints
- Health probe endpoints (`live`/`ready`)
- Standardized DRF exception response format
- Structured JSON logging baseline

### How AI features work (technical summary)
- All AI logic is behind `ai/services.py`.
- Interface-style abstractions define contracts for interview, scoring, estimation, optimization, proof analysis, and challenge generation.
- `MockAIService` provides deterministic behavior for local runs/tests:
  - rule-based interview expert system
  - top-K tagging + checklist generation
  - heuristic time estimation
  - deterministic greedy schedule optimizer
  - proof similarity analysis with thresholding and quality metrics
  - automatic question + todo generation on mismatch
- `OpenAIAdapter` is provided as a swappable integration shell with TODO markers for real LLM/vision/embedding APIs.
- Controllers and tasks use `get_ai_service()` so provider migration does not require API refactors.
