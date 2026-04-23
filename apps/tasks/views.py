"""
TON — Task Views

CRITICAL SECURITY RULES:
- Company submission queries ALWAYS filter by both task_id AND company ownership.
  Filtering by task_id alone would allow a malicious company to read another
  company's submissions by changing the task_id in the request.
- Students cannot see other students' submissions — ever.
- Task feed uses select_related + .only() to prevent N+1 and column over-fetching.
"""

from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.authentication.permissions import IsStudent, IsCompany
from apps.authentication.throttles import TaskSubmitThrottle
from apps.companies.models import Company
from apps.students.models import StudentProfile
from .models import Task, Submission, TaskStatus, SubmissionStatus
from .serializers import (
    TaskFeedSerializer,
    TaskDetailSerializer,
    TaskCreateSerializer,
    SubmissionCreateSerializer,
    SubmissionCompanySerializer,
    SubmissionStudentSerializer,
    SubmissionReviewSerializer,
)


class TaskFeedView(APIView):
    """
    GET /api/tasks/feed/
    Student's personalized task feed — filtered by their sectors, sorted by deadline.
    Uses select_related + .only() to avoid N+1 and over-fetching.
    """
    permission_classes = [IsStudent]

    def get(self, request):
        student = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)

        # CORRECT — select_related pre-fetches company in one JOIN
        # .only() fetches only needed columns — critical on Railway's shared DB
        tasks = (
            Task.objects
            .select_related('company')
            .filter(
                status=TaskStatus.ACTIVE,
                is_deleted=False,
                sector__in=student.sectors if student.sectors else [],
            )
            .order_by('deadline')
            .only(
                'id', 'title', 'sector', 'skill_tags', 'deadline',
                'submissions_count', 'company__company_name', 'company__logo_url',
            )
        )

        # Manual pagination
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 10))
        start = (page - 1) * page_size
        end = start + page_size
        total = tasks.count()

        serializer = TaskFeedSerializer(tasks[start:end], many=True)
        return Response({
            'results': serializer.data,
            'total': total,
            'page': page,
            'page_size': page_size,
            'has_next': end < total,
        })


class TaskDetailView(APIView):
    """GET /api/tasks/<task_id>/"""
    permission_classes = [IsStudent]

    def get(self, request, task_id):
        task = get_object_or_404(
            Task.objects.select_related('company'),
            id=task_id,
            is_deleted=False,
        )
        serializer = TaskDetailSerializer(task, context={'request': request})
        return Response(serializer.data)


class TaskCreateView(APIView):
    """POST /api/tasks/create/ — verified companies only."""
    permission_classes = [IsCompany]

    def post(self, request):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        serializer = TaskCreateSerializer(
            data=request.data, context={'company': company}
        )
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        return Response({
            'task_id': str(task.id),
            'status': task.status,
            'created_at': task.created_at,
        }, status=status.HTTP_201_CREATED)


class TaskCloseView(APIView):
    """PATCH /api/tasks/<task_id>/close/ — company closes own task."""
    permission_classes = [IsCompany]

    def patch(self, request, task_id):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)
        task = get_object_or_404(Task, id=task_id, company=company, is_deleted=False)
        task.status = TaskStatus.CLOSED
        task.save(update_fields=['status'])
        return Response({'task_id': str(task.id), 'status': task.status})


class SubmissionCreateView(APIView):
    """
    POST /api/tasks/<task_id>/submit/
    Student submits to a task. Throttled at 3 per hour.
    Triggers NikoScore activity + reliability recalculation via signal.
    """
    permission_classes = [IsStudent]
    throttle_classes = [TaskSubmitThrottle]

    def post(self, request, task_id):
        student = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)
        task = get_object_or_404(Task, id=task_id, is_deleted=False, status=TaskStatus.ACTIVE)

        # Check deadline
        if task.deadline < timezone.now():
            return Response(
                {'error': 'This task deadline has passed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check max submissions cap
        if task.max_submissions and task.submissions_count >= task.max_submissions:
            return Response(
                {'error': 'This task has reached its maximum number of submissions.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # unique_together enforced at DB level — serializer catches the duplicate
        if Submission.objects.filter(task=task, student=student).exists():
            return Response(
                {'error': 'You have already submitted to this task.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SubmissionCreateSerializer(
            data=request.data,
            context={'task': task, 'student': student},
        )
        serializer.is_valid(raise_exception=True)
        submission = serializer.save()

        # post_save signal fires NikoScore recalculation automatically
        return Response({
            'submission_id': str(submission.id),
            'submitted_at': submission.submitted_at,
        }, status=status.HTTP_201_CREATED)


class TaskSubmissionsView(APIView):
    """
    GET /api/tasks/<task_id>/submissions/
    Company views submissions on THEIR OWN task only.
    CRITICAL: Always filter by BOTH task_id AND company — never task_id alone.
    """
    permission_classes = [IsCompany]

    def get(self, request, task_id):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)

        # CORRECT — enforce company ownership at query level
        task = get_object_or_404(Task, id=task_id, company=company, is_deleted=False)

        submissions = (
            Submission.objects
            .select_related('student', 'student__nikoscore')
            .filter(task=task)
            .order_by('-submitted_at')
            .only(
                'id', 'content_text', 'file_url', 'external_link',
                'company_score', 'company_feedback',
                'status', 'submitted_at', 'reviewed_at',
                'student__id', 'student__full_name',
                'student__nikoscore__total_score',
            )
        )

        serializer = SubmissionCompanySerializer(submissions, many=True)
        return Response(serializer.data)


class SubmissionReviewView(APIView):
    """
    PATCH /api/tasks/submissions/<submission_id>/review/
    Company scores a submission 1–5. Triggers NikoScore quality recalculation via signal.
    """
    permission_classes = [IsCompany]

    def patch(self, request, submission_id):
        company = get_object_or_404(Company, user=request.user, is_deleted=False)

        # Verify company owns the task this submission belongs to
        submission = get_object_or_404(
            Submission,
            id=submission_id,
            task__company=company,
        )

        serializer = SubmissionReviewSerializer(submission, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response({
            'submission_id': str(submission.id),
            'reviewed_at': submission.reviewed_at,
            'message': 'Review saved. NikoScore update queued.',
        })


class SubmissionAbandonView(APIView):
    """
    PATCH /api/tasks/submissions/<submission_id>/abandon/
    Student withdraws their submission before company review.
    Applies -2 reliability penalty via signal.
    Only the submitting student can abandon their own submission.
    """
    permission_classes = [IsStudent]

    def patch(self, request, submission_id):
        student = get_object_or_404(StudentProfile, user=request.user, is_deleted=False)
        submission = get_object_or_404(
            Submission,
            id=submission_id,
            student=student,
            status=SubmissionStatus.SUBMITTED,
        )
        submission.status = 'abandoned'
        submission.save(update_fields=['status'])
        # Signal fires reliability penalty
        return Response({'message': 'Submission abandoned.'})
