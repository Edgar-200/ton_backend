"""
TON — Invitation Serializers

contact_released=True is the ONLY condition under which student contact
details are returned to a company. Enforced here in get_student_contact().

TWO CHECKS required before releasing contact:
  1. obj.contact_released is True (student accepted)
  2. The requesting user is the company that sent the invitation

Both must pass — one check alone is insufficient.
"""

from django.conf import settings
from django.utils import timezone
from datetime import timedelta

from rest_framework import serializers
from .models import Invitation, InvitationType


class InvitationStudentViewSerializer(serializers.ModelSerializer):
    """
    What a student sees in their invitation inbox.
    Company details shown. Student contact NOT relevant here (it's their own invitation).
    """
    company_name = serializers.CharField(source='company.company_name', read_only=True)
    company_logo = serializers.URLField(source='company.logo_url', read_only=True)
    company_sector = serializers.CharField(source='company.sector', read_only=True)

    class Meta:
        model = Invitation
        fields = [
            'id',
            'company_name',
            'company_logo',
            'company_sector',
            'invitation_type',
            'message',
            'status',
            'sent_at',
            'viewed_at',
            'responded_at',
            'expires_at',
        ]


class InvitationCompanyViewSerializer(serializers.ModelSerializer):
    """
    What a company sees in their sent invitations list.
    Student name and NikoScore total shown. Contact details conditionally via get_student_contact.
    """
    student_name = serializers.CharField(source='student.full_name', read_only=True)
    student_id = serializers.UUIDField(source='student.id', read_only=True)
    student_nikoscore = serializers.SerializerMethodField()
    student_contact = serializers.SerializerMethodField()

    class Meta:
        model = Invitation
        fields = [
            'id',
            'student_id',
            'student_name',
            'student_nikoscore',
            'student_contact',
            'invitation_type',
            'status',
            'contact_released',
            'sent_at',
            'viewed_at',
            'responded_at',
            'expires_at',
        ]

    def get_student_nikoscore(self, obj):
        try:
            return obj.student.nikoscore.total_score
        except Exception:
            return 0

    def get_student_contact(self, obj):
        """
        THE PRIVACY GATE — contact details only released when:
          1. contact_released is True (student accepted the invitation)
          2. The requesting user is the company that sent it

        Returns None in all other cases — never raises an error.
        A unit test MUST assert this returns null when contact_released=False.
        """
        request = self.context.get('request')
        if (
            obj.contact_released
            and request
            and request.user.is_authenticated
            and request.user.role == 'company'
            and hasattr(request.user, 'company_profile')
            and obj.company.user == request.user
        ):
            return {
                'email': obj.student.user.email,
            }
        return None  # Never raises — always returns null safely


class InvitationCreateSerializer(serializers.Serializer):
    """
    POST /api/invitations/send/
    Company sends invitation to a student from watchlist.
    """
    student_id = serializers.UUIDField()
    invitation_type = serializers.ChoiceField(choices=InvitationType.choices)
    message = serializers.CharField(max_length=1000, min_length=20)

    def validate_student_id(self, value):
        from apps.students.models import StudentProfile
        try:
            student = StudentProfile.objects.get(id=value, is_deleted=False)
        except StudentProfile.DoesNotExist:
            raise serializers.ValidationError('Student not found.')

        # Only invite verified students
        if student.verification_status != 'verified':
            raise serializers.ValidationError(
                'You can only invite DIT-verified students.'
            )

        self.context['student'] = student
        return value

    def validate(self, data):
        company = self.context['company']
        student = self.context.get('student')

        if not student:
            return data

        # Check for existing active invitation
        existing = Invitation.objects.filter(
            company=company,
            student=student,
            status__in=['sent', 'viewed'],
        ).exists()

        if existing:
            raise serializers.ValidationError(
                'An active invitation to this student already exists.'
            )

        return data

    def create(self, validated_data):
        company = self.context['company']
        student = self.context['student']
        expires_at = timezone.now() + timedelta(days=settings.INVITATION_EXPIRY_DAYS)

        return Invitation.objects.create(
            company=company,
            student=student,
            invitation_type=validated_data['invitation_type'],
            message=validated_data['message'],
            expires_at=expires_at,
        )


class InvitationRespondSerializer(serializers.Serializer):
    """
    PATCH /api/invitations/<id>/respond/
    Student accepts or declines. Both responses earn reliability points.
    """
    response = serializers.ChoiceField(choices=['accepted', 'declined'])
