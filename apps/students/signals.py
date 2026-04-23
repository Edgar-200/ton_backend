"""
TON — Student Signals

Auto-creates StudentProfile when a student User is saved.
Triggers NikoScore recalculation when profile fields change.

CRITICAL: Always use update_fields when saving inside a post_save signal.
Saving the full object re-triggers the signal → infinite loop.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.authentication.models import User
from .models import StudentProfile


@receiver(post_save, sender=User)
def create_student_profile(sender, instance, created, **kwargs):
    """
    Auto-create StudentProfile when a student User is first created.
    Profile data (full_name, dit_student_id, etc.) is seeded from
    the registration serializer after this signal fires.
    """
    if created and instance.role == User.Role.STUDENT:
        StudentProfile.objects.get_or_create(user=instance)


@receiver(post_save, sender=StudentProfile)
def trigger_nikoscore_on_profile_update(sender, instance, created, **kwargs):
    """
    Recalculate the NikoScore profile component whenever the StudentProfile is saved.
    Triggered by: bio updates, photo uploads, sector changes, DIT verification.

    Delayed import to avoid circular imports between students and nikoscore apps.
    """
    # Avoid re-triggering during nikoscore engine saves
    update_fields = kwargs.get('update_fields')
    if update_fields and set(update_fields) == {'profile_completion_pct'}:
        return  # Skip — this save was triggered by completion recalc, not profile change

    try:
        from apps.nikoscore.engine import NikoScoreEngine
        NikoScoreEngine.recalculate_profile_component(instance)
    except Exception:
        pass  # Never block a profile save due to scoring engine failure
