"""
TON — Password Reset & Change Test Suite

Tests:
  ✔ Forgot password always returns 200 (no enumeration)
  ✔ Reset token is single-use
  ✔ Reset token expires correctly
  ✔ Invalid token returns 400
  ✔ Password change requires correct current password
  ✔ New password must differ from current
  ✔ Passwords must match confirmation
  ✔ Full end-to-end flow: forgot → token → reset → login with new password
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch
from rest_framework.test import APIClient
from rest_framework import status

from apps.authentication.models import User, PasswordResetToken


def _make_verified_user(email='user@dit.ac.tz', password='OldPass99', role='student'):
    user = User.objects.create_user(
        email=email, password=password, role=role,
        is_verified=True, is_active=True,
    )
    return user


class ForgotPasswordTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('forgot-password')
        self.user = _make_verified_user()

    @patch('apps.notifications.services._send_email', return_value=True)
    def test_returns_200_for_registered_email(self, mock_email):
        response = self.client.post(self.url, {'email': self.user.email}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)

    @patch('apps.notifications.services._send_email', return_value=True)
    def test_returns_200_for_unknown_email_no_enumeration(self, mock_email):
        """Always returns 200 — never reveals whether email exists."""
        response = self.client.post(
            self.url, {'email': 'notregistered@example.com'}, format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Email must NOT be sent for unknown address
        self.assertFalse(mock_email.called)

    @patch('apps.notifications.services._send_email', return_value=True)
    def test_creates_reset_token_in_db(self, _):
        self.client.post(self.url, {'email': self.user.email}, format='json')
        self.assertTrue(
            PasswordResetToken.objects.filter(user=self.user, used=False).exists()
        )

    @patch('apps.notifications.services._send_email', return_value=True)
    def test_invalidates_old_tokens_on_new_request(self, _):
        """Only one valid token per user at a time."""
        # Create first token
        self.client.post(self.url, {'email': self.user.email}, format='json')
        first_token = PasswordResetToken.objects.get(user=self.user)

        # Request another
        self.client.post(self.url, {'email': self.user.email}, format='json')

        first_token.refresh_from_db()
        self.assertTrue(first_token.used)
        # New token should now exist
        self.assertEqual(
            PasswordResetToken.objects.filter(user=self.user, used=False).count(), 1
        )


class ResetPasswordTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('reset-password')
        self.user = _make_verified_user()

    def _make_token(self, expired=False, used=False):
        import secrets
        token_str = secrets.token_hex(32)
        expires_at = (
            timezone.now() - timedelta(minutes=1)
            if expired
            else timezone.now() + timedelta(minutes=30)
        )
        return PasswordResetToken.objects.create(
            user=self.user,
            token=token_str,
            expires_at=expires_at,
            used=used,
        )

    def test_valid_token_resets_password(self):
        token = self._make_token()
        response = self.client.post(self.url, {
            'token': token.token,
            'new_password': 'BrandNew99',
            'confirm_password': 'BrandNew99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('BrandNew99'))

        token.refresh_from_db()
        self.assertTrue(token.used)  # Single-use — must be marked used

    def test_expired_token_returns_400(self):
        token = self._make_token(expired=True)
        response = self.client.post(self.url, {
            'token': token.token,
            'new_password': 'BrandNew99',
            'confirm_password': 'BrandNew99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_used_token_returns_400(self):
        token = self._make_token(used=True)
        response = self.client.post(self.url, {
            'token': token.token,
            'new_password': 'BrandNew99',
            'confirm_password': 'BrandNew99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_token_returns_400(self):
        response = self.client.post(self.url, {
            'token': 'a' * 64,
            'new_password': 'BrandNew99',
            'confirm_password': 'BrandNew99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_mismatched_passwords_return_400(self):
        token = self._make_token()
        response = self.client.post(self.url, {
            'token': token.token,
            'new_password': 'BrandNew99',
            'confirm_password': 'DifferentPass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Token must NOT be consumed on validation failure
        token.refresh_from_db()
        self.assertFalse(token.used)

    def test_token_is_single_use(self):
        """Using a token twice — second attempt must be rejected."""
        token = self._make_token()
        # First use — success
        self.client.post(self.url, {
            'token': token.token,
            'new_password': 'BrandNew99',
            'confirm_password': 'BrandNew99',
        }, format='json')
        # Second use — must fail
        response = self.client.post(self.url, {
            'token': token.token,
            'new_password': 'AnotherPass99',
            'confirm_password': 'AnotherPass99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('apps.notifications.services._send_email', return_value=True)
    def test_full_forgot_reset_login_flow(self, mock_email):
        """End-to-end: forgot → reset → login with new password."""
        # Step 1: Request reset
        forgot_resp = self.client.post(
            reverse('forgot-password'),
            {'email': self.user.email},
            format='json',
        )
        self.assertEqual(forgot_resp.status_code, status.HTTP_200_OK)

        # Step 2: Get token from DB (simulating what would arrive via email)
        token = PasswordResetToken.objects.get(user=self.user, used=False)

        # Step 3: Reset password
        reset_resp = self.client.post(self.url, {
            'token': token.token,
            'new_password': 'ResetPass99',
            'confirm_password': 'ResetPass99',
        }, format='json')
        self.assertEqual(reset_resp.status_code, status.HTTP_200_OK)

        # Step 4: Login with new password
        login_resp = self.client.post(reverse('login'), {
            'email': self.user.email,
            'password': 'ResetPass99',
        }, format='json')
        self.assertEqual(login_resp.status_code, status.HTTP_200_OK)
        self.assertIn('access', login_resp.data)


class PasswordChangeTest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.url = reverse('change-password')
        self.user = _make_verified_user(password='CurrentPass99')
        self.client.force_authenticate(user=self.user)

    def test_correct_current_password_changes_successfully(self):
        response = self.client.post(self.url, {
            'current_password': 'CurrentPass99',
            'new_password': 'NewSecure99',
            'confirm_password': 'NewSecure99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewSecure99'))

    def test_wrong_current_password_returns_400(self):
        response = self.client.post(self.url, {
            'current_password': 'WrongPassword',
            'new_password': 'NewSecure99',
            'confirm_password': 'NewSecure99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_new_password_same_as_current_returns_400(self):
        response = self.client.post(self.url, {
            'current_password': 'CurrentPass99',
            'new_password': 'CurrentPass99',
            'confirm_password': 'CurrentPass99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_confirm_password_mismatch_returns_400(self):
        response = self.client.post(self.url, {
            'current_password': 'CurrentPass99',
            'new_password': 'NewSecure99',
            'confirm_password': 'DifferentPass',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_returns_401(self):
        self.client.force_authenticate(user=None)
        response = self.client.post(self.url, {
            'current_password': 'CurrentPass99',
            'new_password': 'NewSecure99',
            'confirm_password': 'NewSecure99',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
