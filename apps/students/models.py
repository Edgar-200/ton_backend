"""
TON — Student Profile Model

One-to-one with users where role='student'.
Auto-created via Django signal when a student User is saved.

VERIFICATION STATES (4, not 3 — many developers miss this):
  unsubmitted → (student uploads DIT ID) → pending → verified | rejected

KEY DESIGN DECISIONS:
- sectors stored as JSONField list — no M2M table at MVP
- profile_completion_pct is a cached value, recalculated on every profile save
- dit_id_document_url is a Cloudinary URL — admin reviews the document visually
- Soft delete via SoftDeleteModel — never hard-delete students
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.authentication.base_models import SoftDeleteModel


class CourseChoices(models.TextChoices):
    CIVIL_ENGINEERING = 'civil_engineering', 'Civil Engineering'
    ICT = 'ict', 'Information & Communication Technology'
    ELECTRICAL = 'electrical', 'Electrical Engineering'
    ARCHITECTURE = 'architecture', 'Architecture'
    BUSINESS = 'business', 'Business Administration'
    MECHANICAL = 'mechanical', 'Mechanical Engineering'
    WATER = 'water', 'Water Resources Engineering'
    OTHER = 'other', 'Other'


class VerificationStatus(models.TextChoices):
    UNSUBMITTED = 'unsubmitted', 'Unsubmitted'   # No DIT ID uploaded yet
    PENDING = 'pending', 'Pending'                 # Uploaded, awaiting admin review
    VERIFIED = 'verified', 'Verified'              # Admin approved
    REJECTED = 'rejected', 'Rejected'              # Admin rejected with note


class StudentProfile(SoftDeleteModel):
    """
    Extended profile for role='student' users.
    Signal-created on User.post_save. Seeded with registration data.
    """

    user = models.OneToOneField(
        'authentication.User',
        on_delete=models.CASCADE,
        related_name='student_profile',
    )
    full_name = models.CharField(max_length=200)
    dit_student_id = models.CharField(max_length=50, unique=True)
    course = models.CharField(max_length=100, choices=CourseChoices.choices)
    year_of_study = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        # Postgraduate = 5
    )

    # Bio — min 50 words earns profile score points
    bio = models.TextField(blank=True, max_length=1000)

    # Cloudinary URLs — never store binary data in DB
    profile_photo_url = models.URLField(max_length=500, blank=True)
    dit_id_document_url = models.URLField(max_length=500, blank=True)  # Admin only

    # DIT Verification — 4 states
    verification_status = models.CharField(
        max_length=15,
        choices=VerificationStatus.choices,
        default=VerificationStatus.UNSUBMITTED,
        db_index=True,
    )
    verification_note = models.TextField(blank=True)  # Rejection reason shown to student

    # Sectors of interest — JSONField list, e.g. ['tech', 'agri', 'business']
    # No M2M table at MVP — adds join complexity for zero benefit at this scale
    sectors = models.JSONField(default=list)

    # Cached profile completion percentage — recalculated on every profile save
    profile_completion_pct = models.IntegerField(default=0)

    class Meta:
        db_table = 'student_profiles'
        verbose_name = 'Student Profile'
        verbose_name_plural = 'Student Profiles'

    def __str__(self):
        return f'{self.full_name} ({self.dit_student_id})'

    def calculate_profile_completion(self):
        """
        Calculates profile completion percentage.
        Used to display progress bar on dashboard and to compute NikoScore profile component.
        """
        score = 0
        total = 7

        if self.full_name:
            score += 1
        if self.dit_student_id:
            score += 1
        if self.course:
            score += 1
        if self.year_of_study:
            score += 1
        if self.bio and len(self.bio.split()) >= 50:
            score += 1
        if self.profile_photo_url:
            score += 1
        if len(self.sectors) >= 2:
            score += 1

        return int((score / total) * 100)

    def save(self, *args, **kwargs):
        self.profile_completion_pct = self.calculate_profile_completion()
        super().save(*args, **kwargs)

    @property
    def has_bio_min_words(self):
        return len(self.bio.split()) >= 50 if self.bio else False
