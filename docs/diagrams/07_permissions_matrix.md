# Permissions Matrix (Role vs API)

| API Endpoint | Student | Expert |
|---|---:|---:|
| `POST /api/auth/register/` | Yes | Yes |
| `POST /api/auth/token/` | Yes | Yes |
| `POST /api/interview/start/` | Yes | No |
| `POST /api/interview/message/` | Yes | No |
| `GET /api/objectives/` | Yes (own) | No |
| `POST /api/objectives/` | Yes | No |
| `POST /api/objectives/{id}/tasks/` | Yes (own) | No |
| `POST /api/schedule/optimize/` | Yes | No |
| `POST /api/sessions/{id}/complete/` | Yes (own) | No |
| `GET /api/proofs/{id}/analysis/` | Yes (own) | No |
| `GET /api/challenges/` | Yes (own) | No |
| `POST /api/ai/tagging/informatics/` | Yes | Yes |
| `POST /api/ai/tagging/legal/` | Yes | Yes |
| `POST /api/ai/challenges/generate/` | Yes | Yes |
| `POST /api/ai/time-estimate/` | Yes | Yes |

## Notes
- Role gates are enforced in DRF permissions (`IsStudent`) plus ownership checks in views.
- Swagger/OpenAPI is available for endpoint verification.
