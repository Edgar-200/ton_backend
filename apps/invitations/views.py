"""
TON — Invitation Views

Invitation lifecycle:
  Company sends → Student views → Student accepts or declines
  → If accepted: contact_released=True, company gets student email
  → Either way: +5 reliability points for responding

PRIVACY: contact details are NEVER exposed before acceptance.
The serializer enforces this — not the view.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.authentication.permissions import IsStudent, IsCompany
from apps.authentication.throttles import InvitationSendThrottle
from apps.companies.models import Company
from apps.students.models import StudentProfile
from apps.notifications.services import NotificationService
from .models import Invitation, InvitationStatus
from .serializers import (
    InvitationStudentViewSerializer,
    InvitationCompanyViewSerializer,
    InvitationCreateSerializer,
    InvitationRespondSerializer,
)


class SendInvitationView(APIView):
    """
    POST /api/invitations/send/
    Verified company sends invitation to a watchlisted, verified student.
    Throttled at 20 per company per day.
    """
    permission_classes = [IsCompany]
    throttle_classes = [InvitationSendThrottle]

    def post(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        serializer = InvitationCreateSerializer(
            data=request.data,
            context={'company': company, 'request': request},
        )
        serializer.is_valid(raise_exception=True)
        invitation = serializer.save()

        # Notify student — email + SMS
        NotificationService.send_invitation_received(invitation)

        return Response({
            'invitation_id': str(invitation.id),
            'sent_at': invitation.sent_at,
            'status': invitation.status,
        }, status=status.HTTP_201_CREATED)


class ReceivedInvitationsView(APIView):
    """
    GET /api/invitations/received/
    Student's invitation inbox. Marks unviewed as viewed on retrieval.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        student = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)

        invitations = (
            Invitation.objects
            .select_related('company')
            .filter(student=student)
            .order_by('-sent_at')
        )

        # Mark sent → viewed for all unread invitations
        unread = invitations.filter(status=InvitationStatus.SENT)
        for inv in unread:
            inv.mark_viewed()

        serializer = InvitationStudentViewSerializer(invitations, many=True)
        return Response(serializer.data)


class SentInvitationsView(APIView):
    """
    GET /api/invitations/sent/
    Company views all invitations they have sent with current status.
    """
    permission_classes = [IsCompany]

    def get(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)

        invitations = (
            Invitation.objects
            .select_related('student', 'student__nikoscore', 'student__user')
            .filter(company=company)
            .order_by('-sent_at')
        )

        serializer = InvitationCompanyViewSerializer(
            invitations, many=True, context={'request': request}
        )
        return Response(serializer.data)


class RespondToInvitationView(APIView):
    """
    PATCH /api/invitations/<id>/respond/
    Student accepts or declines.

    On accept:
      - contact_released=True → company can now see student email
      - Company notified with student contact details
      - +5 reliability points (responding earns points — not just accepting)

    On decline:
      - Company notified (without contact details)
      - +5 reliability points (same — responding professionally is the signal)
    """
    permission_classes = [IsStudent]

    def patch(self, request, invitation_id):
        student = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)
        invitation = get_object_or_404(
            Invitation,
            id=invitation_id,
            student=student,
            status__in=[InvitationStatus.SENT, InvitationStatus.VIEWED],
        )

        # Check expiry
        if invitation.is_expired_by_date:
            invitation.expire()
            return Response(
                {'error': 'This invitation has expired.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = InvitationRespondSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        response_choice = serializer.validated_data['response']

        if response_choice == 'accepted':
            invitation.accept()
            # Notify company — with contact details (contact_released=True now)
            NotificationService.send_invitation_accepted(invitation)
        else:
            invitation.decline()
            # Notify company — without contact details
            NotificationService.send_invitation_declined(invitation)

        # Trigger reliability component recalculation via signal
        # (Signal fires on invitation post_save when status changes)

        return Response({
            'invitation_id': str(invitation.id),
            'status': invitation.status,
        })
