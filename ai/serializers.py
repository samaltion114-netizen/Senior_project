"""Serializers for AI endpoints."""
from __future__ import annotations

from rest_framework import serializers


class InterviewStartSerializer(serializers.Serializer):
    pass


class InterviewMessageSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField()
    message = serializers.CharField(max_length=2000)


class VoiceMessageSerializer(serializers.Serializer):
    conversation_id = serializers.IntegerField(required=False)
    message = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    transcript = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    language = serializers.CharField(max_length=16, required=False, default="en")

    def validate(self, attrs):
        message = (attrs.get("message") or attrs.get("transcript") or "").strip()
        if not message:
            raise serializers.ValidationError("Either 'message' or 'transcript' is required.")
        attrs["message"] = message
        attrs["transcript"] = message
        return attrs


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


class GoalGenerationRequestSerializer(serializers.Serializer):
    goal = serializers.CharField(max_length=255)
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


#
# Expert-system transport schemas
#


class DomainOptionSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=12)
    label = serializers.CharField(max_length=120)
    description = serializers.CharField()


class StartSessionRequestSerializer(serializers.Serializer):
    domain = serializers.CharField(max_length=16)
    kb_path = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=500)


class SubmitAnswerRequestSerializer(serializers.Serializer):
    answer = serializers.JSONField()


class QuestionPayloadSerializer(serializers.Serializer):
    node_id = serializers.CharField(max_length=120)
    variant_id = serializers.CharField(max_length=120)
    text_ar = serializers.CharField()
    text_en = serializers.CharField()
    type = serializers.CharField(max_length=24)
    fact_key = serializers.CharField(max_length=120)
    scale_min = serializers.IntegerField(required=False, allow_null=True)
    scale_max = serializers.IntegerField(required=False, allow_null=True)
    numeric_min = serializers.FloatField(required=False, allow_null=True)
    numeric_max = serializers.FloatField(required=False, allow_null=True)
    choices_ar = serializers.ListField(child=serializers.CharField(), required=False, default=list)
    choices_en = serializers.ListField(child=serializers.CharField(), required=False, default=list)


class ProgressPayloadSerializer(serializers.Serializer):
    answered_count = serializers.IntegerField()
    question_number = serializers.IntegerField()
    estimated_total = serializers.IntegerField()
    percent = serializers.FloatField()
    can_go_back = serializers.BooleanField()


class StartSessionResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=64)
    domain = serializers.CharField(max_length=16)
    start_node = serializers.CharField(max_length=120)


class QuestionEnvelopeResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=64)
    finished = serializers.BooleanField()
    question = QuestionPayloadSerializer(required=False, allow_null=True)
    progress = ProgressPayloadSerializer()
    previous_answer = serializers.JSONField(required=False, allow_null=True)


class SubmitAnswerResponseSerializer(serializers.Serializer):
    recorded = serializers.BooleanField()
    fact_key = serializers.CharField(required=False, allow_null=True, max_length=120)
    fact_value = serializers.JSONField(required=False, allow_null=True)
    next_node = serializers.CharField(required=False, allow_null=True, max_length=120)
    is_finished = serializers.BooleanField()
    progress = ProgressPayloadSerializer()


class SessionStateResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=64)
    domain = serializers.CharField(max_length=16)
    current_node_id = serializers.CharField(max_length=120)
    kb_path = serializers.CharField(required=False, allow_null=True, allow_blank=True, max_length=500)
    max_questions = serializers.IntegerField(required=False, allow_null=True)
    answers = serializers.JSONField()
    facts = serializers.JSONField()
    history = serializers.ListField(child=serializers.CharField(), default=list)
    presented_questions = serializers.JSONField()
    answer_log = serializers.JSONField()
    is_finished = serializers.BooleanField()
    goal_filter = serializers.JSONField(required=False, allow_null=True)
    final_output = serializers.JSONField(required=False, allow_null=True)
    progress = ProgressPayloadSerializer()


class GoalSummarySerializer(serializers.Serializer):
    goal_id = serializers.CharField(max_length=120)
    goal_name = serializers.CharField(max_length=255)
    fit_score_percent = serializers.FloatField()


class GapResolutionItemSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    action = serializers.CharField()


class FinalResultResponseSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=64)
    domain = serializers.CharField(max_length=16)
    selected_goal = GoalSummarySerializer(required=False, allow_null=True)
    fit_score = serializers.FloatField(required=False, allow_null=True)
    why_selected = serializers.ListField(child=serializers.CharField(), default=list)
    strengths = serializers.ListField(child=serializers.CharField(), default=list)
    alternative_goal = GoalSummarySerializer(required=False, allow_null=True)
    gaps = serializers.ListField(child=serializers.CharField(), default=list)
    gap_resolution_plan = GapResolutionItemSerializer(many=True, default=list)
    next_steps = serializers.ListField(child=serializers.CharField(), default=list)
    result = serializers.JSONField(default=dict)
