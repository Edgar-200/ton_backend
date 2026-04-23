"""
TON — Invitation Model

Full invitation lifecycle: sent → viewed → accepted | declined

CRITICAL PRIVACY GATE: contact_released
  - A company NEVER sees a student's email or phone until contact_released=True
  - contact_released is set True ONLY when the student accepts
  - Enforced in InvitationDetailSerializer via conditional SerializerMethodField
  - Write a unit test asserting contact is null when contact_released=False

UNIQUE CONSTRAINT:
  Only one ACTIVE invitation per company-student pair.
  A new invitation is only allowed if the previous was declined or expired.
  Enforced via UniqueConstraint with condition on status.

CASCADE RULES:
  PROTECT on both company and student FKs — invitation history needed for
  dispute resolution. Records must survive soft-deletes of either party.

EXPIRY:
  Invitations expire after 14 days (INVITATION_EXPIRY_DAYS setting).
  Expired invitations are auto-closed by the expire_invitations management command.
"""

import uuid
from django.db import models
from django.db.models import Q
from apps.authentication.base_models import UUIDModel


class InvitationType(models.TextChoices):
    INTERNSHIP = 'internship', 'Internship'
    PART_TIME = 'part_time', 'Part-Time'
    FULL_TIME = 'full_time', 'Full-Time'


class InvitationStatus(models.TextChoices):
    SENT = 'sent', 'Sent'
    VIEWED = 'viewed', 'Viewed'
    ACCEPTED = 'accepted', 'Accepted'
    DECLINED = 'declined', 'Declined'
    EXPIRED = 'expired', 'Expired'


class Invitation(UUIDModel):
    """
    Company sends an invitation to a student from their watchlist.
    Contact details are only exchanged after student acceptance.
    """

    company = models.ForeignKey(
        'companies.Company',
        on_delete=models.PROTECT,  # History needed for dispute resolution
        related_name='invitations_sent',
    )
    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.PROTECT,  # History must survive student soft-delete
        related_name='invitations_received',
    )

    invitation_type = models.CharField(
        max_length=12,
        choices=InvitationType.choices,
    )
    message = models.TextField(max_length=1000)

    status = models.CharField(
        max_length=10,
        choices=InvitationStatus.choices,
        default=InvitationStatus.SENT,
        db_index=True,
    )

    # THE PRIVACY GATE
    # True only after student accepts — triggers contact exchange
    # Company sees null for student contact until this is True
    contact_released = models.BooleanField(default=False)

    sent_at = models.DateTimeField(auto_now_add=True)
    viewed_at = models.DateTimeField(null=True, blank=True)      # Set when student opens
    responded_at = models.DateTimeField(null=True, blank=True)   # Set on accept/decline
    expires_at = models.DateTimeField()                           # 14 days from sent_at

    class Meta:
        db_table = 'invitations'
        indexes = [
            models.Index(fields=['student', 'status']),   # Student inbox query
            models.Index(fields=['company', 'status']),   # Company sent invitations
        ]
        constraints = [
            # Only one ACTIVE invitation per company-student pair
            # A new invitation is only allowed if the previous was declined or expired
            models.UniqueConstraint(
                fields=['company', 'student'],
                condition=Q(status__in=['sent', 'viewed']),
                name='unique_active_invitation',
            )
        ]

    def __str__(self):
        return f'{self.company.company_name} → {self.student.full_name} ({self.status})'

    def mark_viewed(self):
        from django.utils import timezone
        if self.status == InvitationStatus.SENT:
            self.status = InvitationStatus.VIEWED
            self.viewed_at = timezone.now()
            self.save(update_fields=['status', 'viewed_at'])

    def accept(self):
        from django.utils import timezone
        self.status = InvitationStatus.ACCEPTED
        self.responded_at = timezone.now()
        self.contact_released = True  # THE MOMENT contact is unlocked
        self.save(update_fields=['status', 'responded_at', 'contact_released'])

    def decline(self):
        from django.utils import timezone
        self.status = InvitationStatus.DECLINED
        self.responded_at = timezone.now()
        # contact_released stays False — company never gets contact on decline
        self.save(update_fields=['status', 'responded_at'])

    def expire(self):
        self.status = InvitationStatus.EXPIRED
        self.save(update_fields=['status'])

    @property
    def is_active(self):
        return self.status in [InvitationStatus.SENT, InvitationStatus.VIEWED]

    @property
    def is_expired_by_date(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at and self.is_active
