"""
TON — Company Model

One-to-one with users where role='company'.

CRITICAL RULES:
- verification_status != 'verified' → company is BLOCKED from ALL write operations
  (posting tasks, viewing submissions, sending invitations)
  This is enforced at the IsCompany permission class level, not in individual views.

- onboarding_stage reflects the three-stage company funnel:
    1 = Curated (founder-selected, pre-launch partners)
    2 = DIT Network (warm introductions via DIT institutional trust)
    3 = Open Verified (any company that passes BRELA + quality review)

- brela_number is Tanzania's business registration number (BRELA = Business
  Registrations and Licensing Agency). Required and unique.

- PROTECT cascade on tasks — deleting a company must never silently delete tasks
  that have student submissions.
"""

import uuid
from django.db import models
from apps.authentication.base_models import SoftDeleteModel


class VerificationStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'


class Company(SoftDeleteModel):
    """
    Company profile. Always starts as pending — admin must verify before any
    platform activity is allowed.
    """

    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='company_profile',
    )

    company_name = models.CharField(max_length=200)

    # Tanzania's business registration number — must be unique
    brela_number = models.CharField(max_length=100, unique=True)

    # Cloudinary URL — admin reviews this document visually
    brela_document_url = models.URLField(max_length=500, blank=True)

    sector = models.CharField(max_length=100)
    contact_person = models.CharField(max_length=200)
    logo_url = models.URLField(max_length=500, blank=True)
    website = models.URLField(blank=True)

    # Admin verification — companies always start pending
    verification_status = models.CharField(
        max_length=10,
        choices=VerificationStatus.choices,
        default=VerificationStatus.PENDING,
        db_index=True,
    )
    verification_note = models.TextField(blank=True)  # Rejection reason

    # Three-stage company onboarding funnel
    onboarding_stage = models.IntegerField(default=1)  # 1=curated, 2=DIT, 3=open

    class Meta:
        db_table = 'companies'
        verbose_name = 'Company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return f'{self.company_name} ({self.verification_status})'

    @property
    def is_verified(self):
        return self.verification_status == VerificationStatus.VERIFIED


class Watchlist(models.Model):
    """
    Junction table — companies save students they are monitoring.
    No status field at MVP: presence in table = actively watched.
    CASCADE on both sides — watchlist is ephemeral data.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='watchlist_entries',
    )
    student = models.ForeignKey(
        'students.StudentProfile',
        on_delete=models.CASCADE,
        related_name='watchlisted_by',
    )
    saved_at = models.DateTimeField(auto_now_add=True)

    # Private company note about the student — never shown to student
    note = models.TextField(blank=True, max_length=500)

    class Meta:
        db_table = 'watchlist'
        unique_together = [['company', 'student']]

    def __str__(self):
        return f'{self.company.company_name} → {self.student.full_name}'
