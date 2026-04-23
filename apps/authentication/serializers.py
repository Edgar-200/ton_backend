"""
TON — Authentication Serializers

Handles: student registration, company registration, OTP verification,
login, and JWT token pair with role embedded in payload.

VERIFICATION FLOW:
  1. POST /register/student/  → creates User + StudentProfile
                                generates 6-digit OTP (stored hashed)
                                sends OTP via EMAIL (guaranteed) + SMS if phone given
                                returns { user_id, email, delivery_channels }
                                NO TOKEN ISSUED HERE

  2. POST /verify-otp/        → checks email + OTP code
                                on success: clears OTP, sets is_verified=True
                                issues JWT access + refresh tokens
                                ONLY place tokens are issued

CRITICAL: NEVER issue JWT tokens at registration.
Email OTP delivery is GUARANTEED. SMS is additional when phone is provided.
"""

import re
import random
import string
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from apps.notifications.services import NotificationService


class TONTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Embeds role into the JWT payload.
    Avoids a DB query on every request just to determine the user's role.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['role'] = user.role
        token['email'] = user.email
        return token


# ─────────────────────────────────────────────
# STUDENT REGISTRATION
# ─────────────────────────────────────────────

class StudentRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(max_length=200)
    dit_student_id = serializers.CharField(max_length=50)
    course = serializers.CharField(max_length=100)
    year_of_study = serializers.IntegerField(min_value=1, max_value=5)
    # Phone is optional — OTP always goes to email; SMS is bonus when provided
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value.lower()

    def validate_dit_student_id(self, value):
        from apps.students.models import StudentProfile
        if StudentProfile.objects.filter(dit_student_id=value).exists():
            raise serializers.ValidationError('DIT student ID already registered.')
        return value.strip()

    def validate_phone(self, value):
        """Normalise to E.164 +255XXXXXXXXX if provided. Reject obviously invalid numbers."""
        if not value:
            return None
        normalised = _normalise_tz_phone(value)
        if not normalised:
            raise serializers.ValidationError(
                'Invalid phone number. Use Tanzanian format: 07XXXXXXXX or +255XXXXXXXXX'
            )
        return normalised

    def create(self, validated_data):
        phone = validated_data.pop('phone', None)
        otp = _generate_otp()
        expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role=User.Role.STUDENT,
            phone=phone,
        )
        user.otp_code = make_password(otp)   # stored hashed — never plaintext
        user.otp_expires_at = expires_at
        user.otp_attempts = 0
        user.save(update_fields=['otp_code', 'otp_expires_at', 'otp_attempts'])

        # Create student profile (signal also fires, but seed data here)
        from apps.students.models import StudentProfile
        StudentProfile.objects.update_or_create(
            user=user,
            defaults={
                'full_name': validated_data['full_name'],
                'dit_student_id': validated_data['dit_student_id'],
                'course': validated_data['course'],
                'year_of_study': validated_data['year_of_study'],
            }
        )

        # Send OTP — email is guaranteed; SMS added when phone is available
        delivery = NotificationService.send_registration_otp(user, otp)

        return {
            'user_id': str(user.id),
            'email': user.email,
            'role': user.role,
            'delivery_channels': delivery,   # tells frontend where the code was sent
        }


# ─────────────────────────────────────────────
# COMPANY REGISTRATION
# ─────────────────────────────────────────────

class CompanyRegistrationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    company_name = serializers.CharField(max_length=200)
    brela_number = serializers.CharField(max_length=100)
    contact_person = serializers.CharField(max_length=200)
    sector = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already registered.')
        return value.lower()

    def validate_brela_number(self, value):
        from apps.companies.models import Company
        if Company.objects.filter(brela_number=value).exists():
            raise serializers.ValidationError('BRELA number already registered.')
        return value.strip()

    def validate_phone(self, value):
        if not value:
            return None
        normalised = _normalise_tz_phone(value)
        if not normalised:
            raise serializers.ValidationError(
                'Invalid phone number. Use Tanzanian format: 07XXXXXXXX or +255XXXXXXXXX'
            )
        return normalised

    def create(self, validated_data):
        phone = validated_data.pop('phone', None)
        otp = _generate_otp()
        expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            role=User.Role.COMPANY,
            phone=phone,
        )
        user.otp_code = make_password(otp)
        user.otp_expires_at = expires_at
        user.otp_attempts = 0
        user.save(update_fields=['otp_code', 'otp_expires_at', 'otp_attempts'])

        from apps.companies.models import Company
        Company.objects.create(
            user=user,
            company_name=validated_data['company_name'],
            brela_number=validated_data['brela_number'],
            contact_person=validated_data['contact_person'],
            sector=validated_data['sector'],
        )

        delivery = NotificationService.send_registration_otp(user, otp)

        return {
            'user_id': str(user.id),
            'email': user.email,
            'role': user.role,
            'delivery_channels': delivery,
            'message': (
                'Account created. Check your email for the verification code. '
                'Your company will be reviewed by an admin after verification.'
            ),
        }


# ─────────────────────────────────────────────
# OTP VERIFICATION
# ─────────────────────────────────────────────

class OTPVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(
        max_length=6, min_length=6,
        help_text='The 6-digit code sent to your email (and phone if provided).'
    )

    def validate(self, data):
        try:
            user = User.objects.get(email=data['email'].lower())
        except User.DoesNotExist:
            raise serializers.ValidationError({'email': 'No account found with this email.'})

        if user.is_verified:
            raise serializers.ValidationError({'email': 'This account is already verified. Please log in.'})

        if user.is_otp_locked:
            raise serializers.ValidationError({
                'code': (
                    f'Too many failed attempts. Request a new verification code.'
                )
            })

        if user.is_otp_expired:
            raise serializers.ValidationError({
                'code': 'Verification code has expired. Request a new one.'
            })

        if not user.otp_code or not check_password(data['code'], user.otp_code):
            user.increment_otp_attempt()
            remaining = settings.OTP_MAX_ATTEMPTS - user.otp_attempts
            raise serializers.ValidationError({
                'code': f'Incorrect code. {max(0, remaining)} attempt(s) remaining.'
            })

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']

        # Clears code, resets attempts, sets is_verified=True — all in one atomic save
        user.clear_otp()

        # JWT tokens — ONLY issued here, after verified
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role

        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': user.role,
            'profile_complete': _get_profile_complete(user),
            'message': 'Email verified successfully. Welcome to TON!',
        }


# ─────────────────────────────────────────────
# OTP RESEND
# ─────────────────────────────────────────────

class ResendOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        value = value.lower()
        try:
            user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError('No account found with this email.')
        if user.is_verified:
            raise serializers.ValidationError('Account already verified. Please log in.')
        self._user = user
        return value

    def save(self):
        user = self._user
        otp = _generate_otp()

        user.otp_code = make_password(otp)
        user.otp_expires_at = timezone.now() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)
        user.otp_attempts = 0    # Reset on regeneration — important
        user.save(update_fields=['otp_code', 'otp_expires_at', 'otp_attempts'])

        delivery = NotificationService.send_registration_otp(user, otp)

        return {
            'message': 'New verification code sent.',
            'delivery_channels': delivery,
        }


# ─────────────────────────────────────────────
# LOGIN
# ─────────────────────────────────────────────

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        from django.contrib.auth import authenticate
        user = authenticate(email=data['email'].lower(), password=data['password'])

        if not user:
            raise serializers.ValidationError({'non_field_errors': 'Invalid email or password.'})
        if not user.is_active:
            raise serializers.ValidationError({'non_field_errors': 'Account suspended. Contact support.'})
        if not user.is_verified:
            raise serializers.ValidationError({
                'non_field_errors': (
                    'Account not verified. '
                    'Check your email for the verification code, or request a new one.'
                )
            })

        data['user'] = user
        return data

    def save(self):
        user = self.validated_data['user']
        user.touch_last_active()
        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'role': user.role,
            'user_id': str(user.id),
        }


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def _generate_otp() -> str:
    """Generate a cryptographically random 6-digit numeric code."""
    return ''.join(random.choices(string.digits, k=settings.OTP_LENGTH))


def _normalise_tz_phone(raw: str):
    """
    Normalise a Tanzanian phone number to E.164 format (+255XXXXXXXXX).
    Returns None if the number cannot be parsed as a valid Tanzanian number.

    Accepted inputs:
      0712345678    → +255712345678
      255712345678  → +255712345678
      +255712345678 → +255712345678 (already correct)
    """
    cleaned = re.sub(r'[\s\-\(\)]', '', raw.strip())

    if cleaned.startswith('+255') and len(cleaned) == 13:
        return cleaned
    if cleaned.startswith('255') and len(cleaned) == 12:
        return f'+{cleaned}'
    if cleaned.startswith('0') and len(cleaned) == 10:
        return f'+255{cleaned[1:]}'

    return None  # Cannot parse — caller raises ValidationError


def _get_profile_complete(user) -> bool:
    """Return True if the user's profile is sufficiently completed."""
    if user.role == User.Role.STUDENT:
        try:
            return user.student_profile.profile_completion_pct >= 80
        except Exception:
            return False
    return False


# ─────────────────────────────────────────────
# PASSWORD CHANGE (authenticated)
# ─────────────────────────────────────────────

class PasswordChangeSerializer(serializers.Serializer):
    """
    POST /api/auth/change-password/
    Authenticated user changes their own password.
    Requires current password to prevent session-hijack abuse.
    """
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context['request'].user
        if not user.check_password(data['current_password']):
            raise serializers.ValidationError(
                {'current_password': 'Current password is incorrect.'}
            )
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'New passwords do not match.'}
            )
        if data['current_password'] == data['new_password']:
            raise serializers.ValidationError(
                {'new_password': 'New password must differ from the current password.'}
            )
        return data

    def save(self):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        # Notify user that their password was changed
        from apps.notifications.services import NotificationService
        NotificationService.send_password_changed(user)
        return {'message': 'Password changed successfully. Please log in again.'}


# ─────────────────────────────────────────────
# FORGOT PASSWORD (unauthenticated)
# ─────────────────────────────────────────────

class ForgotPasswordSerializer(serializers.Serializer):
    """
    POST /api/auth/forgot-password/
    Generates a reset token and emails a reset link.
    Always returns success — never reveals whether email is registered
    (prevents account enumeration).
    """
    email = serializers.EmailField()

    def save(self):
        import secrets
        from datetime import timedelta
        from django.conf import settings
        from .models import PasswordResetToken

        email = self.validated_data['email'].lower()
        try:
            user = User.objects.get(email=email, is_active=True)
        except User.DoesNotExist:
            # Silent — never reveal whether an email is registered
            return {'message': _RESET_SENT_MSG}

        # Invalidate any previous unused tokens for this user
        PasswordResetToken.objects.filter(user=user, used=False).update(used=True)

        token_str = secrets.token_hex(32)  # 64 hex chars
        expires_at = timezone.now() + timedelta(
            minutes=settings.PASSWORD_RESET_EXPIRY_MINUTES
        )
        PasswordResetToken.objects.create(
            user=user,
            token=token_str,
            expires_at=expires_at,
        )

        from apps.notifications.services import NotificationService
        NotificationService.send_password_reset_link(user, token_str)

        return {'message': _RESET_SENT_MSG}


# ─────────────────────────────────────────────
# RESET PASSWORD (uses token from email link)
# ─────────────────────────────────────────────

class ResetPasswordSerializer(serializers.Serializer):
    """
    POST /api/auth/reset-password/
    Consumes the reset token from the email link and sets a new password.
    Token is single-use and expires after PASSWORD_RESET_EXPIRY_MINUTES.
    """
    token = serializers.CharField(max_length=64)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, data):
        from .models import PasswordResetToken

        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'}
            )

        try:
            reset_token = PasswordResetToken.objects.select_related('user').get(
                token=data['token']
            )
        except PasswordResetToken.DoesNotExist:
            raise serializers.ValidationError(
                {'token': 'Invalid or expired reset link.'}
            )

        if not reset_token.is_valid:
            raise serializers.ValidationError(
                {'token': 'This reset link has expired or already been used. Request a new one.'}
            )

        data['reset_token'] = reset_token
        return data

    def save(self):
        reset_token = self.validated_data['reset_token']
        user = reset_token.user

        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])

        # Mark token used — single-use
        reset_token.used = True
        reset_token.save(update_fields=['used'])

        from apps.notifications.services import NotificationService
        NotificationService.send_password_changed(user)

        return {'message': 'Password reset successfully. You can now log in with your new password.'}


_RESET_SENT_MSG = (
    'If an account with that email exists, a password reset link has been sent. '
    'Check your inbox (and spam folder). The link expires in 30 minutes.'
)
