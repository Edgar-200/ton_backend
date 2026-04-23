"""
TON — Expire Invitations Management Command

Run daily alongside apply_decay:
  0 21 * * *  (21:00 UTC = midnight EAT)

Marks all invitations that have passed their expires_at timestamp
as 'expired'. Students cannot respond to expired invitations.

Usage:
  python manage.py expire_invitations
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Expire invitations that have passed their expiry date.'

    def handle(self, *args, **options):
        from apps.invitations.models import Invitation, InvitationStatus

        now = timezone.now()
        expired = Invitation.objects.filter(
            status__in=[InvitationStatus.SENT, InvitationStatus.VIEWED],
            expires_at__lt=now,
        )

        count = expired.count()
        expired.update(status=InvitationStatus.EXPIRED)

        self.stdout.write(
            self.style.SUCCESS(f'Expired {count} invitations.')
        )
