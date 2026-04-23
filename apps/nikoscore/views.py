"""
TON — NikoScore Views & Serializers

Students see full 4-component breakdown.
Companies see total score ONLY — never component breakdown.
Score history (event log) visible to student for transparency.
"""

from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import serializers

from apps.authentication.permissions import IsStudent, IsCompany
from apps.students.models import StudentProfile
from .models import NikoScore, NikoScoreEvent


# ─────────────────────────────────────────────
# SERIALIZERS
# ─────────────────────────────────────────────

class NikoScoreEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NikoScoreEvent
        fields = [
            'id', 'event_type', 'component', 'delta',
            'score_before', 'score_after', 'reason', 'created_at',
        ]


class NikoScoreStudentSerializer(serializers.ModelSerializer):
    """Full breakdown — student-facing only."""
    score_history = serializers.SerializerMethodField()

    class Meta:
        model = NikoScore
        fields = [
            'total_score',
            'component_profile',
            'component_activity',
            'component_quality',
            'component_reliability',
            'last_calculated_at',
            'calculation_version',
            'score_history',
        ]

    def get_score_history(self, obj):
        events = (
            NikoScoreEvent.objects
            .filter(student=obj.student)
            .order_by('-created_at')[:20]
        )
        return NikoScoreEventSerializer(events, many=True).data


class NikoScoreCompanySerializer(serializers.ModelSerializer):
    """Company view — total score ONLY. No component breakdown."""
    class Meta:
        model = NikoScore
        fields = ['total_score', 'last_calculated_at']


# ─────────────────────────────────────────────
# VIEWS
# ─────────────────────────────────────────────

class MyNikoScoreView(APIView):
    """
    GET /api/nikoscore/my-score/
    Student's own full NikoScore with component breakdown and history.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        student = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)
        ns, _ = NikoScore.objects.get_or_create(student=student)
        return Response(NikoScoreStudentSerializer(ns).data)


class StudentNikoScoreCompanyView(APIView):
    """
    GET /api/nikoscore/student/<id>/
    Company sees only the student's total score — no breakdown.
    """
    permission_classes = [IsCompany]

    def get(self, request, student_id):
        student = get_object_or_404(StudentProfile, id=student_id, is_deleted=False)
        ns = get_object_or_404(NikoScore, student=student)
        return Response(NikoScoreCompanySerializer(ns).data)
