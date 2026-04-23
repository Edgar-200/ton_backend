"""
TON — Apply Activity Decay Management Command

Run daily at midnight EAT via Railway cron:
  0 21 * * *  (21:00 UTC = midnight EAT / UTC+3)

Applies -1 per week decay to the activity component of every student
who has been inactive for 30+ days.

Inactivity is defined as: user.last_active_at < (now - 30 days)

This command is the ONLY place where activity decay is applied.
It is NOT applied in real time. If a student logs in after 45 days,
their activity score has already decayed during their absence.

Usage:
  python manage.py apply_decay
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Apply NikoScore activity decay to students inactive for 30+ days.'

    def handle(self, *args, **options):
        from apps.students.models import StudentProfile
        from apps.nikoscore.engine import NikoScoreEngine
        from django.conf import settings

        cutoff = timezone.now() - timedelta(days=settings.NIKOSCORE_INACTIVITY_DAYS)

        inactive_students = StudentProfile.objects.filter(
            user__last_active_at__lt=cutoff,
            is_deleted=False,
            nikoscore__component_activity__gt=0,
        ).select_related('user', 'nikoscore')

        count = inactive_students.count()
        self.stdout.write(f'Found {count} inactive students for decay processing.')

        success = 0
        failed = 0

        for student in inactive_students:
            try:
                NikoScoreEngine.apply_decay(student)
                success += 1
            except Exception as e:
                failed += 1
                logger.error(f'Decay failed for student {student.id}: {e}')

        self.stdout.write(
            self.style.SUCCESS(
                f'Decay complete. Success: {success}, Failed: {failed}'
            )
        )
