"""
TON — User Model

Base authentication table for ALL roles (student, company, admin).
This is the ONLY table that handles passwords, OTP codes, and phone numbers.

Email is the GUARANTEED delivery channel for OTP — always sent.
SMS via Africa's Talking is sent additionally when phone number is provided.

Key design decisions:
- UUID PK — never expose sequential integers
- role set once at registration, never changes
- OTP stored hashed (make_password), cleared immediately after verification
- otp_code field is max_length=128 to accommodate the hashed value
- last_active_at updated on token refresh — drives activity decay engine
"""

import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password, role, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_verified', True)
        extra_fields.setdefault('is_active', True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Central user table. Extended by student_profiles and companies via OneToOneField.

    RULES:
    - otp_code must be cleared to null immediately after successful verification
    - otp_attempts must be reset to 0 on successful verification AND on OTP regeneration
    - role is set once at registration and never changes
    - is_active=False means soft ban, NOT deletion
    - Email OTP is ALWAYS sent — it is the guaranteed delivery channel
    - SMS OTP is sent additionally when phone is provided
    """

    class Role(models.TextChoices):
        STUDENT = 'student', 'Student'
        COMPANY = 'company', 'Company'
        ADMIN = 'admin', 'Admin'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Login identifier — not username
    email = models.EmailField(unique=True, db_index=True)

    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        # Set once at registration — never allow updates via API
    )

    # Django admin compatibility
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    # Soft ban — set False, never delete
    is_active = models.BooleanField(default=True)

    # OTP verification — True only after successful OTP confirmation
    is_verified = models.BooleanField(default=False)

    # OTP fields — all cleared after successful verification.
    # otp_code is stored HASHED via make_password — max_length=128 to fit the hash.
    otp_code = models.CharField(max_length=128, null=True, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    otp_attempts = models.IntegerField(default=0)  # Locked after OTP_MAX_ATTEMPTS

    # Phone number — optional at model level, collected at registration.
    # When provided: OTP is sent via BOTH email AND Africa's Talking SMS.
    # When absent:   OTP is sent via email ONLY (guaranteed channel).
    # Format: E.164 — +255XXXXXXXXX (normalised in the registration serializer).
    phone = models.CharField(max_length=20, blank=True, null=True)

    # Updated on every token refresh — drives NikoScore activity decay
    last_active_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['role']

    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f'{self.email} ({self.role})'

    def touch_last_active(self):
        """Called on every token refresh to keep activity score alive."""
        self.last_active_at = timezone.now()
        self.save(update_fields=['last_active_at'])

    def clear_otp(self):
        """
        MUST be called immediately after successful OTP verification.
        Leaving otp_code set is a security vulnerability.
        Clears code, resets attempts, marks account as verified.
        """
        self.otp_code = None
        self.otp_expires_at = None
        self.otp_attempts = 0
        self.is_verified = True
        self.save(update_fields=['otp_code', 'otp_expires_at', 'otp_attempts', 'is_verified'])

    def increment_otp_attempt(self):
        self.otp_attempts += 1
        self.save(update_fields=['otp_attempts'])

    @property
    def is_otp_expired(self):
        if not self.otp_expires_at:
            return True
        return timezone.now() > self.otp_expires_at

    @property
    def is_otp_locked(self):
        from django.conf import settings
        return self.otp_attempts >= settings.OTP_MAX_ATTEMPTS


class PasswordResetToken(models.Model):
    """
    Stores a one-time password reset token sent to the user's email.

    Flow:
      1. POST /api/auth/forgot-password/  → creates token, emails link
      2. POST /api/auth/reset-password/   → validates token, sets new password

    Tokens expire after PASSWORD_RESET_EXPIRY_MINUTES (default 30).
    Tokens are single-use — marked used=True immediately on consumption.
    Multiple outstanding tokens are allowed (only the latest matters).
    """
    import uuid as _uuid

    id = models.UUIDField(primary_key=True, default=_uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='password_reset_tokens',
    )
    token = models.CharField(max_length=64, unique=True)  # hex token, not hashed
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    class Meta:
        db_table = 'password_reset_tokens'

    def __str__(self):
        return f'Reset token for {self.user.email} (used={self.used})'

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        return not self.used and not self.is_expired
