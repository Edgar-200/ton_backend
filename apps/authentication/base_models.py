"""
TON — Shared Abstract Base Models

Every concrete model must inherit from these. This enforces:
  - UUID primary keys on every table (never auto-increment integers)
  - Timestamps on every table (created_at, updated_at)
  - Soft delete on critical tables (users, students, companies, tasks, invitations)
"""

import uuid
from django.db import models
from django.utils import timezone


class UUIDModel(models.Model):
    """Provides a UUID primary key. All TON tables use this — never integer PKs."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(UUIDModel):
    """Adds created_at and updated_at to every model. Inherit this, not UUIDModel directly."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteModel(TimeStampedModel):
    """
    Adds soft-delete capability. Used on: users, student_profiles, companies,
    tasks, and invitations.

    CRITICAL: Hard deleting any of these breaks NikoScore audit integrity and
    orphans foreign keys. Always call .soft_delete() instead of .delete().
    """
    is_deleted = models.BooleanField(default=False, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save(update_fields=['is_deleted', 'deleted_at'])

    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save(update_fields=['is_deleted', 'deleted_at'])

    class Meta:
        abstract = True
