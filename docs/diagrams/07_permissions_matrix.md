# Permissions Matrix (Role vs API)

| API Endpoint | Student | Expert | Trainer |
|---|---:|---:|---:|
| `POST /api/auth/register/` | Yes | Yes | Yes |
| `POST /api/auth/token/` | Yes | Yes | Yes |
| `POST /api/interview/start/` | Yes | No | No |
| `POST /api/interview/message/` | Yes | No | No |
| `GET /api/objectives/` | Yes (own) | No | No |
| `POST /api/objectives/` | Yes | No | No |
| `POST /api/objectives/{id}/tasks/` | Yes (own) | No | No |
| `POST /api/schedule/optimize/` | Yes | No | No |
| `POST /api/sessions/{id}/complete/` | Yes (own) | No | No |
| `GET /api/proofs/{id}/analysis/` | Yes (own) | No | No |
| `POST /api/reviews/` | No | No | Yes |
| `GET /api/challenges/` | Yes (own) | No | No |
| `POST /api/ai/tagging/informatics/` | Yes | Yes | Yes |
| `POST /api/ai/tagging/legal/` | Yes | Yes | Yes |
| `POST /api/ai/challenges/generate/` | Yes | Yes | Yes |
| `POST /api/ai/time-estimate/` | Yes | Yes | Yes |

## Notes
- Role gates are enforced in DRF permissions (`IsStudent`, `IsTrainer`) plus ownership checks in views.
- Swagger/OpenAPI is available for endpoint verification.
