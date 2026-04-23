"""
TON — Task & Submission Signals

SIGNAL TRIGGER MAP (from backend logic document):
  post_save on Submission (created)        → recalculate activity + reliability
  post_save on Submission (score set)      → recalculate quality component
  post_save on Submission (abandoned)      → apply reliability penalty
  post_save on Submission (any)            → update task.submissions_count cache

CRITICAL RULE: Always use update_fields when saving inside a post_save signal.
Saving the full object re-triggers the signal → infinite loop.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Submission, Task


@receiver(post_save, sender=Submission)
def update_task_submission_count(sender, instance, created, **kwargs):
    """
    Keeps the cached submissions_count on Task up to date.
    Uses F() for an atomic increment — safe under concurrent submissions.
    Avoids expensive COUNT() queries on every task feed load.
    """
    if created:
        from django.db.models import F
        Task.objects.filter(id=instance.task_id).update(
            submissions_count=F('submissions_count') + 1
        )


@receiver(post_save, sender=Submission)
def trigger_nikoscore_on_submission(sender, instance, created, **kwargs):
    """
    Routes submission events to the NikoScore engine.

    On creation → activity + reliability components recalculated.
    On company review (score set, not yet processed) → quality component.
    On abandoned → reliability penalty applied.

    nikoscore_processed flag prevents the engine from double-counting a review.
    """
    update_fields = kwargs.get('update_fields')

    try:
        from apps.nikoscore.engine import NikoScoreEngine

        if created:
            # New submission — affects activity and reliability
            NikoScoreEngine.recalculate(
                student=instance.student,
                trigger='task_submitted',
                source_id=instance.id,
            )

        elif update_fields and 'status' in update_fields and instance.status == 'abandoned':
            # Abandoned submission — reliability penalty
            NikoScoreEngine.recalculate(
                student=instance.student,
                trigger='submission_abandoned',
                source_id=instance.id,
            )

        elif (
            instance.company_score is not None
            and not instance.nikoscore_processed
            and (update_fields is None or 'company_score' in update_fields)
        ):
            # Company review received — quality component
            NikoScoreEngine.recalculate(
                student=instance.student,
                trigger='task_reviewed',
                source_id=instance.id,
            )
            # Mark processed to prevent double-scoring
            # Use update_fields to avoid re-triggering this signal
            Submission.objects.filter(id=instance.id).update(nikoscore_processed=True)

    except Exception:
        pass  # Never block a submission save due to scoring engine failure
