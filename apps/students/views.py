"""
TON — Student Views

Public profile endpoint requires no auth — designed for WhatsApp/LinkedIn sharing.
All other endpoints require student auth.
Private fields (dit_id_document_url, email) never appear in public responses.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.authentication.permissions import IsStudent
from apps.tasks.models import Task
from apps.invitations.models import Invitation
from .models import StudentProfile
from .serializers import (
    StudentPublicSerializer,
    StudentPrivateSerializer,
    StudentProfileUpdateSerializer,
    DITVerificationUploadSerializer,
)


class StudentProfileView(APIView):
    """
    GET  /api/students/profile/  → full private profile
    PATCH /api/students/profile/ → update allowed fields only
    """
    permission_classes = [IsStudent]

    def get(self, request):
        profile = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)
        serializer = StudentPrivateSerializer(profile)
        return Response(serializer.data)

    def patch(self, request):
        profile = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)
        serializer = StudentProfileUpdateSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Signal fires NikoScore profile component recalculation after save
        return Response(StudentPrivateSerializer(profile).data)


class DITVerificationView(APIView):
    """
    POST /api/students/verify-dit/
    Student uploads Cloudinary URL of DIT ID document.
    Status moves from unsubmitted → pending for admin review.
    """
    permission_classes = [IsStudent]

    def post(self, request):
        profile = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)
        serializer = DITVerificationUploadSerializer(profile, data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response({
            'verification_status': profile.verification_status,
            'message': 'Document submitted. Admin will review within 24 hours.',
        })


class StudentPublicProfileView(APIView):
    """
    GET /api/students/public-profile/<id>/
    No auth required — designed for shareable URLs.
    CRITICAL: Only whitelisted fields via StudentPublicSerializer.
    Never exposes email, DIT ID, submissions, or company feedback.
    """
    permission_classes = [AllowAny]

    def get(self, request, student_id):
        # .only() call is critical — prevents accidental field leakage
        profile = get_object_or_404(
            StudentProfile.objects
            .select_related('nikoscore')
            .only(
                'id', 'full_name', 'course', 'year_of_study', 'sectors',
                'bio', 'profile_photo_url', 'verification_status', 'created_at',
                'nikoscore__total_score',
            ),
            id=student_id,
            is_deleted=False,
        )
        serializer = StudentPublicSerializer(profile)
        # Conditionally expose watchlist/invite CTA data for logged-in companies
        data = serializer.data
        if request.user.is_authenticated and request.user.role == 'company':
            try:
                from apps.companies.models import Watchlist
                data['is_watchlisted'] = Watchlist.objects.filter(
                    company=request.user.company_profile,
                    student=profile
                ).exists()
            except Exception:
                data['is_watchlisted'] = False
        return Response(data)


class StudentDashboardView(APIView):
    """
    GET /api/students/dashboard/
    Aggregated dashboard data in a single response.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        profile = get_object_or_404(
            StudentProfile.objects.select_related('nikoscore'),
            user=request.user,
            is_deleted=False,
        )

        # NikoScore data
        try:
            ns = profile.nikoscore
            nikoscore_data = {
                'total_score': ns.total_score,
                'component_profile': ns.component_profile,
                'component_activity': ns.component_activity,
                'component_quality': ns.component_quality,
                'component_reliability': ns.component_reliability,
                'last_calculated_at': ns.last_calculated_at,
            }
        except Exception:
            nikoscore_data = {
                'total_score': 0, 'component_profile': 0, 'component_activity': 0,
                'component_quality': 0, 'component_reliability': 0, 'last_calculated_at': None,
            }

        # Recent submissions (last 5)
        from apps.tasks.models import Submission
        from apps.tasks.serializers import SubmissionStudentSerializer
        recent_subs = (
            Submission.objects
            .select_related('task', 'task__company')
            .filter(student=profile)
            .exclude(status='abandoned')
            .order_by('-submitted_at')[:5]
        )

        # Pending invitations
        pending_inv_count = Invitation.objects.filter(
            student=profile,
            status__in=['sent', 'viewed'],
        ).count()

        # Active tasks count in student's sectors
        active_tasks_count = Task.objects.filter(
            status='active',
            is_deleted=False,
            sector__in=profile.sectors,
        ).count()

        return Response({
            'nikoscore': nikoscore_data,
            'recent_submissions': SubmissionStudentSerializer(recent_subs, many=True).data,
            'pending_invitations_count': pending_inv_count,
            'active_tasks_count': active_tasks_count,
            'profile_completion_pct': profile.profile_completion_pct,
            'verification_status': profile.verification_status,
        })


class StudentSubmissionListView(APIView):
    """
    GET /api/students/submissions/
    Paginated list of the authenticated student's own submissions.
    NEVER exposes company_score or company_feedback.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        from apps.tasks.models import Submission
        from apps.tasks.serializers import SubmissionStudentSerializer

        student = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)

        status_filter = request.query_params.get('status')  # optional: submitted/reviewed/abandoned
        qs = (
            Submission.objects
            .select_related('task', 'task__company')
            .filter(student=student)
            .order_by('-submitted_at')
        )
        if status_filter:
            qs = qs.filter(status=status_filter)

        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        start = (page - 1) * page_size
        end = start + page_size
        total = qs.count()

        return Response({
            'results': SubmissionStudentSerializer(qs[start:end], many=True).data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_next': end < total,
        })
