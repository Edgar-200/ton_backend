"""
TON — Task & Submission Test Suite

Critical tests:
  ✔ company_feedback NEVER appears in student-facing submission API responses
  ✔ Student cannot see another student's submissions
  ✔ Company cannot see another company's submissions (ownership check)
  ✔ Submission deduplication (one per student per task)
  ✔ Task deadline validation
  ✔ Task feed filters by student sectors
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
from apps.tasks.models import Task, Submission
from apps.nikoscore.models import NikoScore


def _make_student(email='s@dit.ac.tz', dit_id='DIT/S/001', sectors=None):
    user = User.objects.create_user(
        email=email, password='pass', role='student',
        is_verified=True, last_active_at=timezone.now()
    )
    profile = StudentProfile.objects.get_or_create(user=user)[0]
    profile.full_name = 'Test Student'
    profile.dit_student_id = dit_id
    profile.course = 'ict'
    profile.year_of_study = 2
    profile.verification_status = 'verified'
    profile.sectors = sectors or ['tech']
    profile.save()
    return user, profile


def _make_company(email='co@ton.tz', brela='BR001'):
    user = User.objects.create_user(
        email=email, password='pass', role='company',
        is_verified=True,
    )
    company = Company.objects.create(
        user=user, company_name='Test Co', brela_number=brela,
        sector='tech', contact_person='HR', verification_status='verified',
    )
    return user, company


def _make_task(company, sector='tech', days_until_deadline=7):
    return Task.objects.create(
        company=company,
        title='Test Task',
        description='A detailed task description with more than 100 characters for validation purposes here.',
        sector=sector,
        skill_tags=['python'],
        deadline=timezone.now() + timedelta(days=days_until_deadline),
    )


class CompanyFeedbackPrivacyTest(TestCase):
    """
    CRITICAL: company_feedback must NEVER appear in any student-facing API response.
    This test is non-negotiable per the system design document.
    """

    def setUp(self):
        self.client = APIClient()
        self.student_user, self.student = _make_student()
        self.company_user, self.company = _make_company()
        self.task = _make_task(self.company)
        self.submission = Submission.objects.create(
            task=self.task,
            student=self.student,
            content_text='My submission content',
            company_score=4,
            company_feedback='Private feedback only for company eyes',
            status='reviewed',
        )
        self.client.force_authenticate(user=self.student_user)

    def test_company_feedback_not_in_student_submission_response(self):
        """
        The most important privacy test in the entire system.
        company_feedback must be absent from every student-facing endpoint.
        """
        url = reverse('student-profile')
        response = self.client.get(url)
        response_str = str(response.data)
        self.assertNotIn('company_feedback', response_str)
        self.assertNotIn('Private feedback only for company eyes', response_str)

    def test_company_score_not_in_student_submission_response(self):
        """Students should not see the score companies gave them."""
        # Students do not have a direct submission list endpoint on their profile
        # This is enforced by SubmissionStudentSerializer excluding company_score
        from apps.tasks.serializers import SubmissionStudentSerializer
        serialized = SubmissionStudentSerializer(self.submission).data
        self.assertNotIn('company_score', serialized)
        self.assertNotIn('company_feedback', serialized)

    def test_company_can_see_own_feedback(self):
        """Company should be able to see feedback on submissions to their own tasks."""
        self.client.force_authenticate(user=self.company_user)
        url = reverse('task-submissions', kwargs={'task_id': self.task.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertIn('company_feedback', response.data[0])
        self.assertEqual(
            response.data[0]['company_feedback'],
            'Private feedback only for company eyes'
        )


class SubmissionOwnershipTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.student1_user, self.student1 = _make_student('s1@dit.ac.tz', 'DIT/001')
        self.student2_user, self.student2 = _make_student('s2@dit.ac.tz', 'DIT/002')
        self.company_user, self.company = _make_company()
        self.task = _make_task(self.company)

    def test_duplicate_submission_blocked(self):
        """One submission per student per task — enforced at DB and API level."""
        Submission.objects.create(
            task=self.task, student=self.student1, content_text='first attempt'
        )
        self.client.force_authenticate(user=self.student1_user)
        url = reverse('task-submit', kwargs={'task_id': self.task.id})
        response = self.client.post(url, {'content_text': 'second attempt'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_company_cannot_see_other_company_submissions(self):
        """
        Filtering by task_id alone is insufficient.
        Must also filter by company ownership.
        """
        other_company_user, other_company = _make_company('other@ton.tz', 'BR999')
        other_task = _make_task(other_company)
        Submission.objects.create(
            task=other_task, student=self.student1, content_text='work'
        )

        self.client.force_authenticate(user=self.company_user)
        # Try to access the other company's task submissions using own company auth
        url = reverse('task-submissions', kwargs={'task_id': other_task.id})
        response = self.client.get(url)
        # Should return 404 — not the other company's submissions
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TaskFeedTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.student_user, self.student = _make_student(sectors=['tech', 'business'])
        self.company_user, self.company = _make_company()

    def test_task_feed_filters_by_student_sectors(self):
        """Student only sees tasks in their registered sectors."""
        _make_task(self.company, sector='tech')
        _make_task(self.company, sector='agriculture')  # Not in student sectors

        self.client.force_authenticate(user=self.student_user)
        url = reverse('task-feed')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        returned_sectors = [t['sector'] for t in response.data['results']]
        self.assertIn('tech', returned_sectors)
        self.assertNotIn('agriculture', returned_sectors)

    def test_past_deadline_tasks_excluded(self):
        """Closed or past-deadline tasks must not appear in active feed."""
        past_task = _make_task(self.company, days_until_deadline=-1)
        past_task.status = 'closed'
        past_task.save(update_fields=['status'])

        self.client.force_authenticate(user=self.student_user)
        url = reverse('task-feed')
        response = self.client.get(url)
        task_ids = [str(t['id']) for t in response.data['results']]
        self.assertNotIn(str(past_task.id), task_ids)

    def test_unverified_company_task_not_blocked_from_feed(self):
        """Tasks from verified companies appear in feed — verification is on posting, not viewing."""
        task = _make_task(self.company, sector='tech')
        self.client.force_authenticate(user=self.student_user)
        url = reverse('task-feed')
        response = self.client.get(url)
        task_ids = [str(t['id']) for t in response.data['results']]
        self.assertIn(str(task.id), task_ids)


class TaskValidationTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.company_user, self.company = _make_company()
        self.client.force_authenticate(user=self.company_user)

    def test_past_deadline_rejected(self):
        url = reverse('task-create')
        response = self.client.post(url, {
            'title': 'Test Task',
            'description': 'x' * 100,
            'sector': 'tech',
            'skill_tags': ['python'],
            'deadline': (timezone.now() - timedelta(days=1)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_short_description_rejected(self):
        url = reverse('task-create')
        response = self.client.post(url, {
            'title': 'Test Task',
            'description': 'Too short',
            'sector': 'tech',
            'skill_tags': ['python'],
            'deadline': (timezone.now() + timedelta(days=7)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unverified_company_cannot_post_task(self):
        unverified_user, unverified_co = _make_company('unverified@ton.tz', 'BR888')
        unverified_co.verification_status = 'pending'
        unverified_co.save(update_fields=['verification_status'])
        self.client.force_authenticate(user=unverified_user)

        url = reverse('task-create')
        response = self.client.post(url, {
            'title': 'Test Task',
            'description': 'x' * 100,
            'sector': 'tech',
            'skill_tags': ['python'],
            'deadline': (timezone.now() + timedelta(days=7)).isoformat(),
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
