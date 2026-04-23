"""
TON — Company Signals

Fires notification emails when admin approves or rejects a company.
This is triggered by StudentProfile.post_save — mirroring how student
DIT verification notifications work.

Note: Admin verification can happen via:
  a) /api/admin/companies/<id>/verify/ (TON admin panel — calls NotificationService directly)
  b) Django admin bulk actions (this signal catches those)

This signal ensures notifications fire regardless of which path is used.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Company


@receiver(post_save, sender=Company)
def notify_on_verification_change(sender, instance, created, **kwargs):
    """
    Send email notification when a company's verification_status changes.
    Only fires on update (not creation — company is always pending on create).

    Uses update_fields check to avoid firing on every unrelated save.
    """
    if created:
        return  # Company is always pending at creation — no notification needed

    update_fields = kwargs.get('update_fields') or set()

    # Only proceed if verification_status was explicitly updated
    if 'verification_status' not in update_fields:
        return

    try:
        from apps.notifications.services import NotificationService
        if instance.verification_status == 'verified':
            NotificationService.send_company_verified(instance.user)
        elif instance.verification_status == 'rejected':
            reason = instance.verification_note or 'No reason provided.'
            NotificationService.send_company_rejected(instance.user, reason)
    except Exception:
        pass  # Never block a company save due to notification failure
