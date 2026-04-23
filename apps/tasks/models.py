"""
TON — Task & Submission Models

Tasks are the central content object of the platform.
Submissions are the most sensitive table — privacy rules strictly enforced.

TASK KEY DECISIONS:
- PROTECT (not CASCADE) on company FK — prevent accidental task deletion
- submissions_count is a CACHED COUNTER updated via signal (not COUNT query at runtime)
- Composite index on (sector, status) — task feed filters on both simultaneously
- sector and status are separately indexed for feed performance

SUBMISSION KEY DECISIONS:
- company_feedback is PRIVATE — never exposed to student in any API response
- unique_together on (task, student) — one submission per student per task
- PROTECT on both task and student FKs — submission history must survive soft-deletes
- nikoscore_processed flag prevents double-processing by the score engine
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.authentication.base_models import SoftDeleteModel, TimeStampedModel


class TaskStatus(models.TextChoices):
    ACTIVE = 'active', 'Active'
    CLOSED = 'closed', 'Closed'
    ARCHIVED = 'archived', 'Archived'


class Task(SoftDeleteModel):
    """Tasks posted by verified companies."""

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,  # Never silently delete tasks that have submissions
        related_name='tasks',
    )

    title = models.CharField(max_length=300)
    description = models.TextField()  # Min 100 chars validated in serializer
    sector = models.CharField(max_length=100, db_index=True)

    # List of skill tags e.g. ['python', 'sql', 'data-analysis']
    skill_tags = models.JSONField(default=list)

    deadline = models.DateTimeField(db_index=True)  # Must be future — validated in serializer
    status = models.CharField(
        max_length=10,
        choices=TaskStatus.choices,
        default=TaskStatus.ACTIVE,
        db_index=True,
    )

    # Optional cap on total submissions
    max_submissions = models.IntegerField(null=True, blank=True)

    # Cached counter — updated via post_save signal on Submission
    # NEVER use COUNT() query at runtime — expensive at scale
    submissions_count = models.IntegerField(default=0)

    class Meta:
        db_table = 'tasks'
        indexes = [
            models.Index(fields=['sector', 'status']),  # Task feed composite
            models.Index(fields=['deadline']),
        ]

    def __str__(self):
        return f'{self.title} — {self.company.company_name}'


class SubmissionStatus(models.TextChoices):
    SUBMITTED = 'submitted', 'Submitted'
    REVIEWED = 'reviewed', 'Reviewed'
    ABANDONED = 'abandoned', 'Abandoned'  # Student withdraws before review


class Submission(TimeStampedModel):
    """
    Student work submitted against a company task.
    Most sensitive table — privacy rules enforced at serializer level.

    NEVER delete rows — use status='abandoned' for student withdrawals.
    company_feedback field is PRIVATE: write a unit test asserting it
    never appears in student-facing API responses.
    """

    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name='submissions',
    )
    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.PROTECT,
        related_name='submissions',
    )

    # Submission content — at least ONE of these required (validated in serializer)
    content_text = models.TextField(blank=True)
    file_url = models.URLField(max_length=500, blank=True)      # Cloudinary URL
    external_link = models.URLField(max_length=500, blank=True)  # GitHub, Figma, Drive

    # Company review — PRIVATE fields
    company_score = models.IntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    # PRIVATE — never exposed to student in any API response
    # Write a unit test that calls the student submission endpoint
    # and asserts company_feedback is NOT in the response keys.
    company_feedback = models.TextField(blank=True)

    status = models.CharField(
        max_length=10,
        choices=SubmissionStatus.choices,
        default=SubmissionStatus.SUBMITTED,
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # NikoScore engine sets this True after processing — prevents double-scoring
    nikoscore_processed = models.BooleanField(default=False)

    class Meta:
        db_table = 'submissions'
        # One submission per student per task — enforced at DB level
        unique_together = [['task', 'student']]
        indexes = [
            models.Index(fields=['task', 'status']),
            models.Index(fields=['student', 'submitted_at']),
        ]

    def __str__(self):
        return f'{self.student.full_name} → {self.task.title}'
