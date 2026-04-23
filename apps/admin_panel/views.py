"""
TON — Admin Panel Views

Full platform admin access. Every admin action is logged with timestamp and reason.
Handles:
  - Company verification queue (approve/reject with reason)
  - Student DIT verification queue (approve/reject with reason)
  - Platform analytics dashboard
  - User management (suspend/ban)

PROTECT cascade rules mean admin cannot hard-delete companies or students
that have related tasks, submissions, or invitations.
Django will raise ProtectedError — handled gracefully in soft-delete views.
"""

from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.authentication.permissions import IsAdmin
from apps.authentication.models import User
from apps.students.models import StudentProfile
from apps.companies.models import Company
from apps.tasks.models import Task, Submission
from apps.invitations.models import Invitation
from apps.notifications.services import NotificationService


# ─────────────────────────────────────────────
# SERIALIZERS
# ─────────────────────────────────────────────

class PendingCompanySerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)
    registered_at = serializers.DateTimeField(source='created_at', read_only=True)

    class Meta:
        model = Company
        fields = [
            'id', 'email', 'company_name', 'brela_number', 'brela_document_url',
            'sector', 'contact_person', 'verification_status',
            'onboarding_stage', 'registered_at',
        ]


class PendingStudentSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = StudentProfile
        fields = [
            'id', 'email', 'full_name', 'dit_student_id', 'course',
            'year_of_study', 'dit_id_document_url', 'verification_status', 'created_at',
        ]


class AdminVerifyActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)

    def validate(self, data):
        if data['action'] == 'reject' and not data.get('reason'):
            raise serializers.ValidationError(
                {'reason': 'A reason is required when rejecting.'}
            )
        return data


# ─────────────────────────────────────────────
# COMPANY VERIFICATION QUEUE
# ─────────────────────────────────────────────

class PendingCompaniesView(APIView):
    """GET /api/admin/companies/pending/"""
    permission_classes = [IsAdmin]

    def get(self, request):
        companies = (
            Company.objects
            .select_related('user')
            .filter(verification_status='pending', is_deleted=False)
            .order_by('created_at')  # FIFO queue — oldest first
        )
        serializer = PendingCompanySerializer(companies, many=True)
        return Response(serializer.data)


class VerifyCompanyView(APIView):
    """PATCH /api/admin/companies/<id>/verify/"""
    permission_classes = [IsAdmin]

    def patch(self, request, company_id):
        company = get_object_or_404(Company, id=company_id)
        serializer = AdminVerifyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')

        if action == 'approve':
            company.verification_status = 'verified'
            company.verification_note = ''
            company.save(update_fields=['verification_status', 'verification_note'])
            NotificationService.send_company_verified(company.user)
        else:
            company.verification_status = 'rejected'
            company.verification_note = reason
            company.save(update_fields=['verification_status', 'verification_note'])
            NotificationService.send_company_rejected(company.user, reason)

        _log_admin_action(
            admin=request.user,
            action=f'company_{action}',
            target_id=str(company.id),
            reason=reason,
        )

        return Response({
            'company_id': str(company.id),
            'verification_status': company.verification_status,
        })


# ─────────────────────────────────────────────
# STUDENT DIT VERIFICATION QUEUE
# ─────────────────────────────────────────────

class PendingDITStudentsView(APIView):
    """GET /api/admin/students/pending-dit/"""
    permission_classes = [IsAdmin]

    def get(self, request):
        students = (
            StudentProfile.objects
            .select_related('user')
            .filter(verification_status='pending', is_deleted=False)
            .order_by('created_at')
        )
        serializer = PendingStudentSerializer(students, many=True)
        return Response(serializer.data)


class VerifyStudentDITView(APIView):
    """PATCH /api/admin/students/<id>/verify-dit/"""
    permission_classes = [IsAdmin]

    def patch(self, request, student_id):
        student = get_object_or_404(StudentProfile, id=student_id)
        serializer = AdminVerifyActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data['action']
        reason = serializer.validated_data.get('reason', '')

        if action == 'approve':
            student.verification_status = 'verified'
            student.verification_note = ''
            student.save(update_fields=['verification_status', 'verification_note'])
            # Signal fires NikoScore profile component recalculation (+10 for DIT verified)
            NotificationService.send_dit_verified(student.user)
        else:
            student.verification_status = 'rejected'
            student.verification_note = reason
            student.save(update_fields=['verification_status', 'verification_note'])
            NotificationService.send_dit_rejected(student.user, reason)

        _log_admin_action(
            admin=request.user,
            action=f'dit_{action}',
            target_id=str(student.id),
            reason=reason,
        )

        return Response({
            'student_id': str(student.id),
            'verification_status': student.verification_status,
        })


# ─────────────────────────────────────────────
# USER MANAGEMENT
# ─────────────────────────────────────────────

class SuspendUserView(APIView):
    """
    PATCH /api/admin/users/<id>/suspend/
    Sets is_active=False — soft ban. Never deletes.
    """
    permission_classes = [IsAdmin]

    def patch(self, request, user_id):
        user = get_object_or_404(User, id=user_id)
        reason = request.data.get('reason', '')

        if not reason:
            return Response(
                {'error': 'Reason is required for suspension.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.is_active = False
        user.save(update_fields=['is_active'])

        _log_admin_action(
            admin=request.user,
            action='user_suspended',
            target_id=str(user.id),
            reason=reason,
        )

        return Response({'message': f'User {user.email} suspended.'})


# ─────────────────────────────────────────────
# ANALYTICS DASHBOARD
# ─────────────────────────────────────────────

class PlatformAnalyticsView(APIView):
    """GET /api/admin/analytics/"""
    permission_classes = [IsAdmin]

    def get(self, request):
        total_students = StudentProfile.objects.filter(is_deleted=False).count()
        verified_students = StudentProfile.objects.filter(
            verification_status='verified', is_deleted=False
        ).count()
        total_companies = Company.objects.filter(is_deleted=False).count()
        verified_companies = Company.objects.filter(
            verification_status='verified', is_deleted=False
        ).count()
        active_tasks = Task.objects.filter(status='active', is_deleted=False).count()
        total_submissions = Submission.objects.count()

        total_invitations = Invitation.objects.count()
        accepted_invitations = Invitation.objects.filter(status='accepted').count()
        invitations_accepted_rate = (
            round((accepted_invitations / total_invitations) * 100, 1)
            if total_invitations > 0 else 0
        )

        # Sector breakdown
        sector_data = (
            Task.objects
            .filter(is_deleted=False)
            .values('sector')
            .annotate(count=Count('id'))
            .order_by('-count')
        )

        return Response({
            'students': {
                'total': total_students,
                'verified': verified_students,
                'pending_dit': StudentProfile.objects.filter(
                    verification_status='pending', is_deleted=False
                ).count(),
            },
            'companies': {
                'total': total_companies,
                'verified': verified_companies,
                'pending': Company.objects.filter(
                    verification_status='pending', is_deleted=False
                ).count(),
            },
            'tasks': {
                'active': active_tasks,
                'total': Task.objects.filter(is_deleted=False).count(),
            },
            'submissions': {
                'total': total_submissions,
                'reviewed': Submission.objects.filter(
                    company_score__isnull=False
                ).count(),
            },
            'invitations': {
                'total': total_invitations,
                'accepted': accepted_invitations,
                'accepted_rate_pct': invitations_accepted_rate,
            },
            'sectors': list(sector_data),
        })


# ─────────────────────────────────────────────
# AUDIT LOGGING
# ─────────────────────────────────────────────

def _log_admin_action(admin, action: str, target_id: str, reason: str = ''):
    """
    Every admin action is logged. Required for governance and dispute resolution.
    If a student or company disputes an admin decision, this log is the record.
    Written directly — not via a signal — to ensure it always fires.
    """
    import logging
    audit_logger = logging.getLogger('ton.admin_audit')
    audit_logger.info(
        f'ADMIN_ACTION | admin={admin.email} | action={action} | '
        f'target={target_id} | reason={reason}'
    )
