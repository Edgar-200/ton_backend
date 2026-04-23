"""
TON — Company Serializers

Companies see only total NikoScore for students — never component breakdown.
Student contact details only exposed via InvitationDetailSerializer (contact_released=True).
"""

from rest_framework import serializers
from .models import Company, Watchlist
from apps.students.models import StudentProfile


class CompanyProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    tasks_posted_count = serializers.SerializerMethodField()
    invitations_sent_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            'id', 'email', 'company_name', 'brela_number', 'sector',
            'contact_person', 'logo_url', 'website', 'verification_status',
            'verification_note', 'onboarding_stage', 'tasks_posted_count',
            'invitations_sent_count', 'created_at',
        ]
        read_only_fields = [
            'id', 'email', 'brela_number', 'verification_status',
            'verification_note', 'onboarding_stage', 'created_at',
        ]

    def get_tasks_posted_count(self, obj):
        return obj.tasks.filter(is_deleted=False).count()

    def get_invitations_sent_count(self, obj):
        return obj.invitations_sent.count()


class CompanyProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = ['company_name', 'sector', 'logo_url', 'contact_person', 'website']


class WatchlistStudentSerializer(serializers.ModelSerializer):
    """Student summary as seen by a company from watchlist — total score only."""
    nikoscore_total = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = ['id', 'full_name', 'course', 'year_of_study',
                  'profile_photo_url', 'verification_status', 'nikoscore_total']

    def get_nikoscore_total(self, obj):
        try:
            return obj.nikoscore.total_score
        except Exception:
            return 0


class WatchlistSerializer(serializers.ModelSerializer):
    student = WatchlistStudentSerializer(read_only=True)

    class Meta:
        model = Watchlist
        fields = ['id', 'student', 'saved_at', 'note']


class WatchlistAddSerializer(serializers.Serializer):
    student_id = serializers.UUIDField()

    def validate_student_id(self, value):
        try:
            student = StudentProfile.objects.get(id=value, is_deleted=False)
        except StudentProfile.DoesNotExist:
            raise serializers.ValidationError('Student not found.')
        self.context['student'] = student
        return value

    def save(self):
        company = self.context['company']
        student = self.context['student']
        entry, created = Watchlist.objects.get_or_create(company=company, student=student)
        return entry, created
