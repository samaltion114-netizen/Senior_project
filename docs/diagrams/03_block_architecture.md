# Block Architecture Diagram

```mermaid
flowchart TD
  UI[Web/Mobile Clients]
  NGINX[Nginx Reverse Proxy]
  APP[Django + DRF + JWT]
  DB[(PostgreSQL)]
  CACHE[(Redis)]
  CELERY[Celery Worker/Beat]
  FILES[Media Storage]
  AIINT[AI Service Interface]
  MOCK[MockAIService]
  OPENAI[OpenAIAdapter TODO]

  UI --> NGINX --> APP
  APP --> DB
  APP --> FILES
  APP --> CACHE
  APP --> AIINT
  AIINT --> MOCK
  AIINT -.provider swap.-> OPENAI
  APP --> CELERY
  CELERY --> CACHE
  CELERY --> DB
  CELERY --> AIINT
```

## Main processing blocks
- Authentication and role checks (JWT + permissions)
- Interview and objective recommendation
- Task estimation and scheduling
- Proof ingestion and analysis
- Bug remediation generation (question + todos)
- Trainer review and escalation
- Daily adaptive challenge generation
