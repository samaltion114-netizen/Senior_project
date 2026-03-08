"""Centralized REST error formatting."""
from __future__ import annotations

from rest_framework import status
from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """Return standardized API error payload."""
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        errors = detail
    elif isinstance(detail, dict):
        message = "Validation error."
        errors = detail
    else:
        message = str(detail)
        errors = {"detail": detail}

    response.data = {
        "success": False,
        "message": message,
        "errors": errors,
        "status_code": response.status_code,
    }
    if response.status_code == status.HTTP_404_NOT_FOUND and not message:
        response.data["message"] = "Not found."
    return response
