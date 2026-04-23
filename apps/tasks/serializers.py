"""
TON — Task & Submission Serializers

SUBMISSION SERIALIZER SPLIT (privacy boundary):
  SubmissionStudentSerializer  → student's own submission (no company_score, no company_feedback)
  SubmissionCompanySerializer  → company reviewing own task submissions (includes score + feedback)

RULES:
  - company_feedback NEVER appears in any student-facing serializer
  - A unit test MUST assert this field is absent from student API responses
  - company_score also never shown to the submitting student
  - Student can only see their OWN submissions
  - Company can only see submissions on THEIR OWN tasks
"""

from django.utils import timezone
from rest_framework import serializers
from .models import Task, Submission, TaskStatus


# ─────────────────────────────────────────────
# TASK SERIALIZERS
# ─────────────────────────────────────────────

class TaskFeedSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for the task feed list.
    Only fields needed to render a task card — not full description.
    """
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    company_logo = serializers.URLField(source='company.logo_url', read_only=True)
    deadline_passed = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'company_name', 'company_logo',
            'sector', 'skill_tags', 'deadline', 'submissions_count',
            'deadline_passed',
        ]

    def get_deadline_passed(self, obj):
        return obj.deadline < timezone.now()


class TaskDetailSerializer(serializers.ModelSerializer):
    """Full task detail — shown when a student opens a specific task."""
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    company_logo = serializers.URLField(source='company.logo_url', read_only=True)
    has_submitted = serializers.SerializerMethodField()

    class Meta:
        model = Task
        fields = [
            'id', 'title', 'description', 'company_name', 'company_logo',
            'sector', 'skill_tags', 'deadline', 'status',
            'submissions_count', 'max_submissions', 'has_submitted',
            'created_at',
        ]

    def get_has_submitted(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        if request.user.role != 'student':
            return False
        try:
            return Submission.objects.filter(
                task=obj, student=request.user.student_profile
            ).exists()
        except Exception:
            return False


class TaskCreateSerializer(serializers.ModelSerializer):
    """POST /api/tasks/create/ — company creates a task."""

    class Meta:
        model = Task
        fields = ['title', 'description', 'sector', 'skill_tags', 'deadline', 'max_submissions']

    def validate_description(self, value):
        if len(value) < 100:
            raise serializers.ValidationError(
                'Task description must be at least 100 characters to give students enough context.'
            )
        return value

    def validate_deadline(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError('Deadline must be a future date and time.')
        return value

    def validate_skill_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('skill_tags must be a list.')
        return value

    def create(self, validated_data):
        company = self.context['company']
        return Task.objects.create(company=company, **validated_data)


# ─────────────────────────────────────────────
# SUBMISSION SERIALIZERS — PRIVACY SPLIT
# ─────────────────────────────────────────────

class SubmissionStudentSerializer(serializers.ModelSerializer):
    """
    For students viewing their own submissions.
    CRITICAL: company_score and company_feedback are EXCLUDED.
    They know it was reviewed (via status/reviewed_at) but never see the score or feedback.
    """
    task_title = serializers.CharField(source='task.title', read_only=True)
    task_sector = serializers.CharField(source='task.sector', read_only=True)

    class Meta:
        model = Submission
        fields = [
            'id', 'task', 'task_title', 'task_sector',
            'content_text', 'file_url', 'external_link',
            'status', 'submitted_at', 'reviewed_at',
            # company_score and company_feedback intentionally ABSENT
        ]


class SubmissionCompanySerializer(serializers.ModelSerializer):
    """
    For companies reviewing submissions on their OWN tasks.
    Includes company_score and company_feedback (both writable).
    Shows student name and NikoScore total — never contact details.
    """
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id = serializers.UUIDField(source='student.id', read_only=True)
    student_nikoscore = serializers.SerializerMethodField()

    class Meta:
        model = Submission
        fields = [
            'id', 'student_id', 'student_name', 'student_nikoscore',
            'content_text', 'file_url', 'external_link',
            'company_score', 'company_feedback',
            'status', 'submitted_at', 'reviewed_at',
            # Student contact details NEVER here — only after invitation accepted
        ]
        read_only_fields = ['id', 'student_id', 'student_name', 'student_nikoscore',
                            'content_text', 'file_url', 'external_link',
                            'submitted_at', 'reviewed_at', 'status']

    def get_student_nikoscore(self, obj):
        try:
            return obj.student.nikoscore.total_score
        except Exception:
            return 0


class SubmissionCreateSerializer(serializers.ModelSerializer):
    """
    POST /api/tasks/<task_id>/submit/
    At least one of content_text, file_url, or external_link is required.
    """

    class Meta:
        model = Submission
        fields = ['content_text', 'file_url', 'external_link']

    def validate(self, data):
        if not any([data.get('content_text'), data.get('file_url'), data.get('external_link')]):
            raise serializers.ValidationError(
                'At least one of content_text, file_url, or external_link is required.'
            )
        return data

    def create(self, validated_data):
        task = self.context['task']
        student = self.context['student']
        return Submission.objects.create(task=task, student=student, **validated_data)


class SubmissionReviewSerializer(serializers.ModelSerializer):
    """
    PATCH /api/tasks/submissions/<id>/review/
    Company sets score (1–5) and optional feedback.
    """

    class Meta:
        model = Submission
        fields = ['company_score', 'company_feedback']

    def validate_company_score(self, value):
        if value not in range(1, 6):
            raise serializers.ValidationError('Score must be between 1 and 5.')
        return value

    def save(self, **kwargs):
        instance = self.instance
        instance.company_score = self.validated_data['company_score']
        instance.company_feedback = self.validated_data.get('company_feedback', '')
        instance.status = 'reviewed'
        instance.reviewed_at = timezone.now()
        instance.save(update_fields=[
            'company_score', 'company_feedback', 'status', 'reviewed_at'
        ])
        return instance
