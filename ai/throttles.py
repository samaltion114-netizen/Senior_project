"""Custom throttles for AI endpoints."""
from rest_framework.throttling import UserRateThrottle


class InterviewThrottle(UserRateThrottle):
    scope = "interview"
