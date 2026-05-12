"""Serializers for AI endpoints."""
from __future__ import annotations

from rest_framework import serializers


class InterviewStartSerializer(serializers.Serializer):
    pass


class InterviewMessageSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField()
    message = serializers.CharField(max_length=2000)


class TaggingChecklistSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=6000)
    domain = serializers.ChoiceField(choices=["informatics", "law"], required=False)


class DailyChallengeRequestSerializer(serializers.Serializer):
    domain = serializers.ChoiceField(choices=["informatics", "law"])
    level = serializers.ChoiceField(choices=["beginner", "intermediate", "advanced"])
    minutes = serializers.IntegerField(min_value=5, max_value=120, default=20)


class TimeEstimateRequestSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(allow_blank=True, default="")
    metadata = serializers.JSONField(required=False, default=dict)


class TaskGenerationRequestSerializer(serializers.Serializer):
    user_level = serializers.ChoiceField(choices=["beginner", "intermediate", "advanced"], required=False, default="intermediate")
    count = serializers.IntegerField(min_value=1, max_value=10, default=5)


class MindmapGenerateRequestSerializer(serializers.Serializer):
    topic = serializers.CharField(min_length=3, max_length=255)
    context = serializers.CharField(required=False, allow_blank=True, default="", max_length=4000)
    max_branches = serializers.IntegerField(min_value=2, max_value=12, default=6)


class ModelWeightSelectSerializer(serializers.Serializer):
    capability = serializers.ChoiceField(
        choices=["all", "interview", "tagging", "time_estimation", "scheduling", "proof_analysis", "challenge_generation"]
    )
    provider = serializers.ChoiceField(choices=["local", "openai", "mock"], default="local")
    model_name = serializers.CharField(max_length=120)
    weight_path = serializers.CharField(max_length=500)
    metadata = serializers.JSONField(required=False, default=dict)
