"""
TON — Invitation Signals

post_save on Invitation when status changes to accepted or declined
→ triggers NikoScore reliability component recalculation.

Responding to an invitation — even declining — earns +5 reliability points.
This is intentional: it rewards professional behaviour.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Invitation


@receiver(post_save, sender=Invitation)
def trigger_nikoscore_on_invitation_response(sender, instance, created, **kwargs):
    """
    When a student responds to an invitation (accepted or declined),
    recalculate their reliability component.

    Always use update_fields to avoid re-triggering this signal.
    """
    if created:
        return  # Only care about updates

    update_fields = kwargs.get('update_fields') or set()

    if 'status' in update_fields and instance.status in ['accepted', 'declined']:
        try:
            from apps.nikoscore.engine import NikoScoreEngine
            NikoScoreEngine.recalculate(
                student=instance.student,
                trigger='invitation_responded',
                source_id=instance.id,
            )
        except Exception:
            pass  # Never block an invitation save due to scoring engine failure
