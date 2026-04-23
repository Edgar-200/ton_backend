"""
TON — Student Serializers

TWO SERIALIZER SPLIT — critical privacy boundary:
  StudentPublicSerializer  → anyone, no auth required (public profile page)
  StudentPrivateSerializer → authenticated student, own profile only

FIELDS NEVER EXPOSED PUBLICLY:
  - dit_student_id
  - dit_id_document_url (admin only — never in any API response)
  - user.email
  - nikoscore component breakdown (total only on public)
  - submission content
  - company_feedback
"""

from rest_framework import serializers
from .models import StudentProfile


# ─────────────────────────────────────────────
# PUBLIC — No auth required
# Shared on WhatsApp, LinkedIn, etc.
# ─────────────────────────────────────────────

class StudentPublicSerializer(serializers.ModelSerializer):
    """
    Safe for unauthenticated access.
    Shows NikoScore total only — never component breakdown.
    Never exposes email, DIT ID, or submission content.
    """
    nikoscore_total = serializers.SerializerMethodField()
    tasks_attempted = serializers.SerializerMethodField()
    member_since = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'full_name',
            'course',
            'year_of_study',
            'bio',
            'sectors',
            'profile_photo_url',
            'verification_status',
            'nikoscore_total',
            'tasks_attempted',
            'member_since',
        ]
        # CRITICAL: dit_student_id, dit_id_document_url, user.email NEVER here

    def get_nikoscore_total(self, obj):
        try:
            return obj.nikoscore.total_score
        except Exception:
            return 0

    def get_tasks_attempted(self, obj):
        return obj.submissions.filter(is_deleted=False).count() if hasattr(obj, 'submissions') else 0


# ─────────────────────────────────────────────
# PRIVATE — Authenticated student, own profile only
# ─────────────────────────────────────────────

class NikoScoreComponentSerializer(serializers.Serializer):
    """Breakdown of all 4 components — student-only, never public."""
    total_score = serializers.IntegerField()
    component_profile = serializers.IntegerField()
    component_activity = serializers.IntegerField()
    component_quality = serializers.IntegerField()
    component_reliability = serializers.IntegerField()
    last_calculated_at = serializers.DateTimeField()


class StudentPrivateSerializer(serializers.ModelSerializer):
    """
    Full profile view — for the authenticated student themselves only.
    Includes email, DIT ID, full NikoScore breakdown.
    """
    email = serializers.EmailField(source='user.email', read_only=True)
    nikoscore = serializers.SerializerMethodField()
    profile_completion_pct = serializers.IntegerField(read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'email',
            'full_name',
            'dit_student_id',
            'course',
            'year_of_study',
            'bio',
            'sectors',
            'profile_photo_url',
            'verification_status',
            'verification_note',
            'profile_completion_pct',
            'nikoscore',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'email', 'dit_student_id', 'verification_status',
            'verification_note', 'profile_completion_pct', 'created_at', 'updated_at',
        ]

    def get_nikoscore(self, obj):
        try:
            ns = obj.nikoscore
            return {
                'total_score': ns.total_score,
                'component_profile': ns.component_profile,
                'component_activity': ns.component_activity,
                'component_quality': ns.component_quality,
                'component_reliability': ns.component_reliability,
                'last_calculated_at': ns.last_calculated_at,
            }
        except Exception:
            return {
                'total_score': 0,
                'component_profile': 0,
                'component_activity': 0,
                'component_quality': 0,
                'component_reliability': 0,
                'last_calculated_at': None,
            }


class StudentProfileUpdateSerializer(serializers.ModelSerializer):
    """
    PATCH /api/students/profile/
    Only fields the student is allowed to self-update.
    role, dit_student_id, verification_status are NOT editable via this serializer.
    """

    class Meta:
        model = StudentProfile
        fields = ['bio', 'sectors', 'profile_photo_url', 'year_of_study', 'course']

    def validate_sectors(self, value):
        allowed = [
            'tech', 'engineering', 'business', 'agriculture',
            'health', 'education', 'finance', 'logistics', 'other'
        ]
        for s in value:
            if s not in allowed:
                raise serializers.ValidationError(f'Invalid sector: {s}')
        return value

    def validate_bio(self, value):
        if value and len(value) > 1000:
            raise serializers.ValidationError('Bio must be 1000 characters or fewer.')
        return value


class DITVerificationUploadSerializer(serializers.ModelSerializer):
    """
    POST /api/students/verify-dit/
    Student uploads their DIT ID document URL (from Cloudinary).
    Sets verification_status from unsubmitted → pending.
    """
    dit_id_document_url = serializers.URLField()

    class Meta:
        model = StudentProfile
        fields = ['dit_id_document_url']

    def validate(self, data):
        profile = self.instance
        if profile.verification_status == 'verified':
            raise serializers.ValidationError('DIT enrollment already verified.')
        if profile.verification_status == 'pending':
            raise serializers.ValidationError('Verification already under review.')
        return data

    def save(self, **kwargs):
        profile = self.instance
        profile.dit_id_document_url = self.validated_data['dit_id_document_url']
        profile.verification_status = 'pending'
        profile.save(update_fields=['dit_id_document_url', 'verification_status'])
        return profile


class StudentDashboardSerializer(serializers.Serializer):
    """
    GET /api/students/dashboard/
    Aggregated dashboard data — one response to fill the full dashboard.
    """
    nikoscore = NikoScoreComponentSerializer()
    recent_submissions = serializers.ListField()
    pending_invitations_count = serializers.IntegerField()
    active_tasks_count = serializers.IntegerField()
    profile_completion_pct = serializers.IntegerField()
    verification_status = serializers.CharField()
