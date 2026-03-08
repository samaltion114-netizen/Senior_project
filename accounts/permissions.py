"""Role-based permissions."""
from rest_framework.permissions import BasePermission


class IsStudent(BasePermission):
    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_student)
