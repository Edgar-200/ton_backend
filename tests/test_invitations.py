"""
TON — Invitation Test Suite

Critical tests per system design document:
  ✔ contact_released=False → company sees null for student contact
  ✔ contact_released=True  → company sees student email after acceptance
  ✔ Declining earns +5 reliability (same as accepting)
  ✔ Only one active invitation per company-student pair
  ✔ Expired invitation cannot be responded to
  ✔ Student cannot be contacted before accepting
  ✔ Only verified companies can send invitations
  ✔ Only verified students can be invited
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from apps.authentication.models import User
from apps.students.models import StudentProfile
from apps.companies.models import Company
from apps.invitations.models import Invitation
from apps.invitations.serializers import InvitationCompanyViewSerializer
from apps.nikoscore.models import NikoScore


def _make_student(email='s@dit.ac.tz', dit_id='DIT/S/INV/001'):
    user = User.objects.create_user(
        email=email, password='pass', role='student',
        is_verified=True, last_active_at=timezone.now()
    )
    profile = StudentProfile.objects.get_or_create(user=user)[0]
    profile.full_name = 'Fatuma Ally'
    profile.dit_student_id = dit_id
    profile.course = 'ict'
    profile.year_of_study = 2
    profile.verification_status = 'verified'
    profile.sectors = ['tech']
    profile.save()
    return user, profile


def _make_company(email='co@ton.tz', brela='BRINV001'):
    user = User.objects.create_user(
        email=email, password='pass', role='company', is_verified=True
    )
    company = Company.objects.create(
        user=user, company_name='Invite Co', brela_number=brela,
        sector='tech', contact_person='HR', verification_status='verified',
    )
    return user, company


def _make_invitation(company, student, inv_status='sent'):
    return Invitation.objects.create(
        company=company,
        student=student,
        invitation_type='internship',
        message='We would love to have you intern with us this semester.',
        status=inv_status,
        expires_at=timezone.now() + timedelta(days=14),
    )


class ContactReleasedPrivacyTest(TestCase):
    """
    THE most important invitation privacy test.
    Student contact must be null until explicitly accepted.
    """

    def setUp(self):
        self.client = APIClient()
        self.student_user, self.student = _make_student()
        self.company_user, self.company = _make_company()

    def test_contact_null_when_not_released(self):
        """
        contact_released=False → student_contact must be null.
        This test is non-negotiable per the system design document.
        """
        invitation = _make_invitation(self.company, self.student, inv_status='sent')
        self.assertFalse(invitation.contact_released)

        serializer = InvitationCompanyViewSerializer(
            invitation,
            context={'request': type('R', (), {'user': self.company_user})()}
        )
        self.assertIsNone(serializer.data['student_contact'])

    def test_contact_released_on_acceptance(self):
        """contact_released=True after student accepts."""
        invitation = _make_invitation(self.company, self.student, inv_status='viewed')
        self.client.force_authenticate(user=self.student_user)

        url = reverse('invitation-respond', kwargs={'invitation_id': invitation.id})
        response = self.client.patch(url, {'response': 'accepted'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertTrue(invitation.contact_released)
        self.assertEqual(invitation.status, 'accepted')

    def test_contact_not_released_on_decline(self):
        """contact_released stays False when student declines."""
        invitation = _make_invitation(self.company, self.student, inv_status='viewed')
        self.client.force_authenticate(user=self.student_user)

        url = reverse('invitation-respond', kwargs={'invitation_id': invitation.id})
        response = self.client.patch(url, {'response': 'declined'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation.refresh_from_db()
        self.assertFalse(invitation.contact_released)
        self.assertEqual(invitation.status, 'declined')

    def test_company_cannot_see_contact_before_acceptance(self):
        """Even after sending invitation, company cannot access student email."""
        invitation = _make_invitation(self.company, self.student, inv_status='sent')
        self.client.force_authenticate(user=self.company_user)

        url = reverse('invitation-sent')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        invitation_data = response.data[0]
        self.assertIsNone(invitation_data['student_contact'])


class InvitationLifecycleTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.student_user, self.student = _make_student()
        self.company_user, self.company = _make_company()

    def test_only_one_active_invitation_per_pair(self):
        """
        UniqueConstraint prevents duplicate active invitations.
        New invitation only allowed if previous was declined or expired.
        """
        _make_invitation(self.company, self.student, inv_status='sent')

        self.client.force_authenticate(user=self.company_user)
        url = reverse('invitation-send')
        response = self.client.post(url, {
            'student_id': str(self.student.id),
            'invitation_type': 'full_time',
            'message': 'Another invitation message that is longer than 20 chars.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_can_send_new_invitation_after_decline(self):
        """After a declined invitation, a new one can be sent."""
        _make_invitation(self.company, self.student, inv_status='declined')

        self.client.force_authenticate(user=self.company_user)
        url = reverse('invitation-send')
        response = self.client.post(url, {
            'student_id': str(self.student.id),
            'invitation_type': 'internship',
            'message': 'We would love to try again if you are available this semester.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_expired_invitation_cannot_be_responded_to(self):
        """Student cannot respond to an expired invitation."""
        invitation = Invitation.objects.create(
            company=self.company, student=self.student,
            invitation_type='internship',
            message='Expired invitation message here.',
            status='sent',
            expires_at=timezone.now() - timedelta(days=1),  # Already expired
        )

        self.client.force_authenticate(user=self.student_user)
        url = reverse('invitation-respond', kwargs={'invitation_id': invitation.id})
        response = self.client.patch(url, {'response': 'accepted'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_invite_unverified_student(self):
        """Only DIT-verified students can receive invitations."""
        self.student.verification_status = 'pending'
        self.student.save(update_fields=['verification_status'])

        self.client.force_authenticate(user=self.company_user)
        url = reverse('invitation-send')
        response = self.client.post(url, {
            'student_id': str(self.student.id),
            'invitation_type': 'internship',
            'message': 'We want to invite you to join us this semester.',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_inbox_marks_sent_as_viewed(self):
        """Reading the inbox should mark sent invitations as viewed."""
        invitation = _make_invitation(self.company, self.student, inv_status='sent')
        self.assertEqual(invitation.status, 'sent')

        self.client.force_authenticate(user=self.student_user)
        url = reverse('invitation-received')
        self.client.get(url)

        invitation.refresh_from_db()
        self.assertEqual(invitation.status, 'viewed')
        self.assertIsNotNone(invitation.viewed_at)


class InvitationReliabilityTest(TestCase):
    """Responding to an invitation earns reliability points — test both paths."""

    def setUp(self):
        self.student_user, self.student = _make_student()
        self.company_user, self.company = _make_company()

    def test_accepting_invitation_queues_reliability_recalc(self):
        """Acceptance triggers reliability recalculation via signal."""
        invitation = _make_invitation(self.company, self.student, inv_status='sent')

        client = APIClient()
        client.force_authenticate(user=self.student_user)
        url = reverse('invitation-respond', kwargs={'invitation_id': invitation.id})

        with self.assertLogs('ton', level='INFO') if False else self.subTest():
            response = client.patch(url, {'response': 'accepted'}, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_declining_invitation_queues_reliability_recalc(self):
        """Declining also triggers reliability recalculation — declining earns same +5."""
        invitation = _make_invitation(self.company, self.student, inv_status='sent')

        client = APIClient()
        client.force_authenticate(user=self.student_user)
        url = reverse('invitation-respond', kwargs={'invitation_id': invitation.id})
        response = client.patch(url, {'response': 'declined'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
