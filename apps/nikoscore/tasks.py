"""
TON — Celery Tasks (nikoscore app)

These tasks wrap NikoScore engine calls for asynchronous processing.
At MVP the Django signals call the engine synchronously (inline).

When to switch to async (Celery):
  - Request p95 latency > 500ms under load
  - Submission review endpoint feels slow to the company
  - Railway log shows signal handlers taking > 200ms

HOW TO MIGRATE:
  In apps/tasks/signals.py and apps/invitations/signals.py,
  replace direct engine calls with:
    recalculate_nikoscore.delay(str(student.id), trigger, str(source_id))

Retry strategy: exponential backoff, max 3 retries, 60s countdown.
"""

from config.celery import app
import logging

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def recalculate_nikoscore(self, student_id: str, trigger: str, source_id: str = None):
    """
    Async NikoScore recalculation.
    Called after submission creation, review, abandonment, or invitation response.

    Args:
        student_id:  UUID string of the StudentProfile
        trigger:     event type (task_submitted, task_reviewed, etc.)
        source_id:   UUID string of the triggering object (submission, invitation)
    """
    try:
        import uuid
        from apps.students.models import StudentProfile
        from apps.nikoscore.engine import NikoScoreEngine

        student = StudentProfile.objects.get(id=uuid.UUID(student_id))
        src = uuid.UUID(source_id) if source_id else None
        NikoScoreEngine.recalculate(student=student, trigger=trigger, source_id=src)
        logger.info(f'[celery] NikoScore recalculated: student={student_id} trigger={trigger}')

    except Exception as exc:
        logger.error(f'[celery] recalculate_nikoscore FAILED: {exc}')
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=2, default_retry_delay=30)
def send_notification_email(self, notification_type: str, payload: dict):
    """
    Async email/SMS notification delivery.
    Used to decouple notification sending from the request lifecycle.

    notification_type:  e.g. 'invitation_received', 'dit_verified'
    payload:            dict of context data (invitation_id, user_id, etc.)
    """
    try:
        from apps.notifications.services import NotificationService

        dispatch = {
            'dit_verified': _notify_dit_verified,
            'dit_rejected': _notify_dit_rejected,
            'invitation_received': _notify_invitation_received,
        }

        handler = dispatch.get(notification_type)
        if handler:
            handler(payload)
            logger.info(f'[celery] notification sent: type={notification_type}')
        else:
            logger.warning(f'[celery] unknown notification_type: {notification_type}')

    except Exception as exc:
        logger.error(f'[celery] send_notification_email FAILED: {exc}')
        raise self.retry(exc=exc)


def _notify_dit_verified(payload):
    from apps.authentication.models import User
    from apps.notifications.services import NotificationService
    user = User.objects.get(id=payload['user_id'])
    NotificationService.send_dit_verified(user)


def _notify_dit_rejected(payload):
    from apps.authentication.models import User
    from apps.notifications.services import NotificationService
    user = User.objects.get(id=payload['user_id'])
    NotificationService.send_dit_rejected(user, payload.get('reason', ''))


def _notify_invitation_received(payload):
    from apps.invitations.models import Invitation
    from apps.notifications.services import NotificationService
    invitation = Invitation.objects.select_related(
        'company', 'student', 'student__user'
    ).get(id=payload['invitation_id'])
    NotificationService.send_invitation_received(invitation)
