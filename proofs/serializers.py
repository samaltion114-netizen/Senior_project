"""Serializers for proof APIs."""
from __future__ import annotations

from rest_framework import serializers

from proofs.models import Challenge, ProgrammingQuestion, Proof, TodoItem


class CompleteSessionSerializer(serializers.Serializer):
    image = serializers.ImageField()
    explanation = serializers.CharField(max_length=5000)

    def validate_image(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Image too large (max 5MB).")
        allowed = {"image/png", "image/jpeg", "image/jpg"}
        if value.content_type not in allowed:
            raise serializers.ValidationError("Only PNG/JPEG images are allowed.")
        return value


class TodoItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = TodoItem
        fields = ("id", "title", "description", "priority", "done")


class ProgrammingQuestionSerializer(serializers.ModelSerializer):
    todo_items = TodoItemSerializer(many=True, read_only=True)

    class Meta:
        model = ProgrammingQuestion
        fields = ("id", "title", "description", "severity", "suggested_fixes", "todo_items")


class ProofSerializer(serializers.ModelSerializer):
    programming_questions = ProgrammingQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = Proof
        fields = ("id", "session", "image", "explanation_text", "ai_analysis", "analysis_status", "programming_questions")
        read_only_fields = ("session", "ai_analysis", "analysis_status")


class ChallengeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Challenge
        fields = ("id", "text", "difficulty", "scheduled_date", "completed")
