"""
TON — NikoScore Models

TWO TABLES:
  NikoScore        → cached score (one row per student, overwritten by engine)
  NikoScoreEvent   → immutable append-only audit log (NEVER updated or deleted)

CRITICAL: NikoScore is always COMPUTED from raw event data.
The nikoscores table stores a CACHE only — it is regenerated from nikoscore_events.
If they conflict, nikoscore_events wins.

NEVER manually set a NikoScore value directly in a view. Always call the engine.

calculation_version is critical for future formula changes:
  When updating the formula (Year 2), set version=2 and backfill all students
  asynchronously. Without this field you cannot safely migrate scores.
"""

import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.authentication.base_models import UUIDModel


class NikoScore(models.Model):
    """
    Cached NikoScore for a student.
    One row per student — enforced by OneToOneField.
    NEVER edited directly — always overwritten by NikoScoreEngine.recalculate().
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.OneToOneField(
        'students.StudentProfile',
        on_delete=models.CASCADE,
        related_name='nikoscore',
    )

    # Total score — sum of all four components. Validators enforce 0–100.
    total_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    # Component scores — each 0–25
    component_profile = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(25)]
    )
    component_activity = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(25)]
    )
    component_quality = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(25)]
    )
    component_reliability = models.IntegerField(
        default=0, validators=[MinValueValidator(0), MaxValueValidator(25)]
    )

    last_calculated_at = models.DateTimeField(auto_now=True)

    # Increment when engine formula changes — enables safe backfill of all students
    calculation_version = models.IntegerField(default=1)

    class Meta:
        db_table = 'nikoscores'

    def __str__(self):
        return f'{self.student.full_name} — {self.total_score}/100'

    def recalculate_total(self):
        """Recomputes and clamps total from components. Always call after updating components."""
        self.total_score = min(
            100,
            self.component_profile
            + self.component_activity
            + self.component_quality
            + self.component_reliability
        )


class EventType(models.TextChoices):
    PROFILE_COMPLETED = 'profile_completed', 'Profile Completed'
    DIT_VERIFIED = 'dit_verified', 'DIT Verified'
    TASK_SUBMITTED = 'task_submitted', 'Task Submitted'
    TASK_REVIEWED = 'task_reviewed', 'Task Reviewed'
    SUBMISSION_ABANDONED = 'submission_abandoned', 'Submission Abandoned'
    INVITATION_RESPONDED = 'invitation_responded', 'Invitation Responded'
    ACTIVITY_DECAY = 'activity_decay', 'Activity Decay'
    PROFILE_UPDATED = 'profile_updated', 'Profile Updated'


class ComponentType(models.TextChoices):
    PROFILE = 'profile', 'Profile'
    ACTIVITY = 'activity', 'Activity'
    QUALITY = 'quality', 'Quality'
    RELIABILITY = 'reliability', 'Reliability'


class NikoScoreEvent(models.Model):
    """
    Immutable audit log. Every score change recorded here.
    Records are NEVER updated or deleted — append only.

    PROTECT on student FK — audit log must survive student soft-delete.
    source_id allows tracing exactly which submission/invitation caused a change.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.PROTECT,  # Audit log must survive all user state changes
        related_name='nikoscore_events',
    )

    event_type = models.CharField(max_length=30, choices=EventType.choices)
    component = models.CharField(max_length=15, choices=ComponentType.choices)

    # Score change — can be negative (penalties)
    delta = models.IntegerField()

    # Snapshots at time of event — for debugging and dispute resolution
    score_before = models.IntegerField()
    score_after = models.IntegerField()

    reason = models.TextField()  # Human-readable: 'Company review score: 4/5'

    # ID of the object that triggered this (submission_id, invitation_id, etc.)
    source_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'nikoscore_events'
        indexes = [
            models.Index(fields=['student', 'created_at']),
        ]

    def __str__(self):
        return f'{self.student.full_name} | {self.event_type} | {self.delta:+d}'

    def save(self, *args, **kwargs):
        # Enforce immutability — raise if trying to update an existing record
        if self.pk and NikoScoreEvent.objects.filter(pk=self.pk).exists():
            raise ValueError('NikoScoreEvent records are immutable. Never update or delete them.')
        super().save(*args, **kwargs)
