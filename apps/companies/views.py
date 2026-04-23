"""
TON — Company Views

All write operations gated by IsCompany (verified only).
Read-only profile view available to unverified companies (IsUnverifiedCompany).
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.authentication.permissions import IsCompany, IsUnverifiedCompany
from apps.tasks.models import Task
from apps.invitations.models import Invitation
from .models import Company, Watchlist
from .serializers import (
    CompanyProfileSerializer,
    CompanyProfileUpdateSerializer,
    WatchlistSerializer,
    WatchlistAddSerializer,
)


class CompanyProfileView(APIView):
    """GET /api/companies/profile/  PATCH /api/companies/profile/"""

    def get_permissions(self):
        if self.request.method == 'GET':
            return [IsUnverifiedCompany()]
        return [IsCompany()]

    def get(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        return Response(CompanyProfileSerializer(company).data)

    def patch(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        serializer = CompanyProfileUpdateSerializer(company, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(CompanyProfileSerializer(company).data)


class CompanyDashboardView(APIView):
    """GET /api/companies/dashboard/"""
    permission_classes = [IsCompany]

    def get(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)

        active_tasks = company.tasks.filter(status='active', is_deleted=False).count()

        from apps.tasks.models import Submission
        total_submissions = Submission.objects.filter(
            task__company=company
        ).count()

        watchlist_count = company.watchlist_entries.count()

        pending_invitations = Invitation.objects.filter(
            company=company, status__in=['sent', 'viewed']
        ).count()

        return Response({
            'active_tasks': active_tasks,
            'total_submissions_received': total_submissions,
            'watchlist_count': watchlist_count,
            'invitations_pending': pending_invitations,
        })


class WatchlistView(APIView):
    """GET /api/companies/watchlist/"""
    permission_classes = [IsCompany]

    def get(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        entries = company.watchlist_entries.select_related(
            'student', 'student__nikoscore'
        ).order_by('-saved_at')
        return Response(WatchlistSerializer(entries, many=True).data)


class WatchlistAddView(APIView):
    """POST /api/companies/watchlist/add/"""
    permission_classes = [IsCompany]

    def post(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        serializer = WatchlistAddSerializer(
            data=request.data, context={'company': company}
        )
        serializer.is_valid(raise_exception=True)
        entry, created = serializer.save()
        if created:
            return Response({'message': 'Student added to watchlist.'}, status=status.HTTP_201_CREATED)
        return Response({'message': 'Already in watchlist.'})


class WatchlistRemoveView(APIView):
    """DELETE /api/companies/watchlist/remove/<id>/"""
    permission_classes = [IsCompany]

    def delete(self, request, entry_id):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        entry = get_object_or_404(Watchlist, id=entry_id, company=company)
        entry.delete()
        return Response({'message': 'Removed from watchlist.'})


class CompanyBRELAUploadView(APIView):
    """
    POST /api/companies/upload-brela/
    Company uploads their BRELA certificate document URL (from Cloudinary).
    Sets brela_document_url for admin review.
    Available to any authenticated company (including unverified — they need
    to upload the document to GET verified).
    """
    permission_classes = [IsUnverifiedCompany]

    def post(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        url = request.data.get('brela_document_url', '').strip()
        if not url:
            return Response(
                {'error': 'brela_document_url is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        company.brela_document_url = url
        # If rejected, allow resubmission → back to pending
        if company.verification_status == 'rejected':
            company.verification_status = 'pending'
            company.save(update_fields=['brela_document_url', 'verification_status'])
        else:
            company.save(update_fields=['brela_document_url'])

        return Response({
            'message': 'Document submitted. Admin will review within 48 hours.',
            'verification_status': company.verification_status,
        })
