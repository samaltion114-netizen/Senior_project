#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://localhost}"

echo "Register student..."
curl -s -X POST "$BASE_URL/api/auth/register/" -H "Content-Type: application/json" \
  -d '{"username":"student1","password":"pass12345","email":"student1@example.com","role":"student","major":"IT"}' >/dev/null

echo "Register trainer..."
curl -s -X POST "$BASE_URL/api/auth/register/" -H "Content-Type: application/json" \
  -d '{"username":"trainer1","password":"pass12345","email":"trainer1@example.com","role":"trainer"}' >/dev/null

STUDENT_TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/token/" -H "Content-Type: application/json" \
  -d '{"username":"student1","password":"pass12345"}' | python -c "import sys, json; print(json.load(sys.stdin)['access'])")
TRAINER_TOKEN=$(curl -s -X POST "$BASE_URL/api/auth/token/" -H "Content-Type: application/json" \
  -d '{"username":"trainer1","password":"pass12345"}' | python -c "import sys, json; print(json.load(sys.stdin)['access'])")

CONVERSATION_ID=$(curl -s -X POST "$BASE_URL/api/interview/start/" \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" -d '{}' | \
  python -c "import sys, json; print(json.load(sys.stdin)['conversation_id'])")

SUGGESTED_JSON=$(curl -s -X POST "$BASE_URL/api/interview/message/" \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"conversation_id\":$CONVERSATION_ID,\"message\":\"I want training in AI backend internship\"}")
OBJECTIVE_TITLE=$(echo "$SUGGESTED_JSON" | python -c "import sys, json; print(json.load(sys.stdin)['recommended_objective']['title'])")
OBJECTIVE_DESC=$(echo "$SUGGESTED_JSON" | python -c "import sys, json; print(json.load(sys.stdin)['recommended_objective']['description'])")

OBJECTIVE_ID=$(curl -s -X POST "$BASE_URL/api/objectives/" \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"title\":\"$OBJECTIVE_TITLE\",\"description\":\"$OBJECTIVE_DESC\",\"suggested_by\":\"ai\",\"status\":\"active\"}" | \
  python -c "import sys, json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "$BASE_URL/api/objectives/$OBJECTIVE_ID/tasks/" \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Implement a classifier","description":"build","metadata":{"complexity":2},"order":1}' >/dev/null

curl -s -X POST "$BASE_URL/api/objectives/$OBJECTIVE_ID/tasks/" \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d '{"title":"Write docs","description":"document the API","metadata":{"complexity":1},"order":2}' >/dev/null

SESSION_ID=$(curl -s -X POST "$BASE_URL/api/schedule/optimize/" \
  -H "Authorization: Bearer $STUDENT_TOKEN" -H "Content-Type: application/json" \
  -d "{\"objective_id\":$OBJECTIVE_ID,\"weekly_availability\":{\"monday\":[{\"start\":\"18:00\",\"end\":\"20:00\"}]},\"max_daily_minutes\":90}" | \
  python -c "import sys, json; print(json.load(sys.stdin)['sessions'][0]['id'])")

PROOF_ID=$(curl -s -X POST "$BASE_URL/api/sessions/$SESSION_ID/complete/" \
  -H "Authorization: Bearer $STUDENT_TOKEN" \
  -F "image=@tests/fixtures/screenshot1.png" \
  -F "explanation=Uploaded proof text for analysis" | \
  python -c "import sys, json; print(json.load(sys.stdin)['id'])")

curl -s -X GET "$BASE_URL/api/proofs/$PROOF_ID/analysis/" -H "Authorization: Bearer $STUDENT_TOKEN"

curl -s -X POST "$BASE_URL/api/reviews/" \
  -H "Authorization: Bearer $TRAINER_TOKEN" -H "Content-Type: application/json" \
  -d "{\"proof\":$PROOF_ID,\"is_bug_confirmed\":true,\"notes\":\"Confirmed bug\"}"

echo
echo "Demo flow completed. Proof ID: $PROOF_ID"
